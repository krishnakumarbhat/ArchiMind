"""
ArchiMind Flask Application
Consolidated web application with authentication and analysis routes.
"""
import os
import sys
import json
import uuid
import logging
import subprocess
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from datetime import datetime
from oauth_utils import (
    init_oauth, init_redis, oauth_bp, get_user_repository_history,
    get_repository_details, save_repository_to_history
)


# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class ApplicationConfig:
    """Application configuration class."""
    
    def __init__(self):
        self.SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
        self.DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/archimind')
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.DATA_PATH = os.path.abspath('./data')
        self.STATUS_FILE_PATH = os.path.join(self.DATA_PATH, 'status.json')
        self.ANONYMOUS_GENERATION_LIMIT = 5
        self.GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
        self.GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')


# Database instance
db = SQLAlchemy()


class User(db.Model, UserMixin):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    analyses = db.relationship('AnalysisLog', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def get_analysis_count(self):
        """Returns the total number of analyses performed by this user."""
        return len(self.analyses)


class AnalysisLog(db.Model):
    """Tracks repository analysis requests for rate limiting."""
    __tablename__ = 'analysis_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    session_id = db.Column(db.String(255), nullable=True, index=True)
    repo_url = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f'<AnalysisLog {self.repo_url} - {self.status}>'


class ArchiMindApplication:
    """Main application class with route handlers."""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.config = ApplicationConfig()
        self._configure_application()
        self._initialize_extensions()
        self._register_routes()
        self._initialize_data_directory()
    
    def _configure_application(self):
        """Configures Flask application settings."""
        self.app.config['SECRET_KEY'] = self.config.SECRET_KEY
        self.app.config['SQLALCHEMY_DATABASE_URI'] = self.config.DATABASE_URL
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = self.config.SQLALCHEMY_TRACK_MODIFICATIONS
    
    def _initialize_extensions(self):
        """Initializes Flask extensions."""
        db.init_app(self.app)
        
        # Initialize OAuth
        init_oauth(self.app)
        self.app.register_blueprint(oauth_bp)
        
        # Initialize Redis
        init_redis()
        
        self.login_manager = LoginManager()
        self.login_manager.login_view = 'login'
        self.login_manager.init_app(self.app)
        
        @self.login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
        
        with self.app.app_context():
            db.create_all()
    
    def _initialize_data_directory(self):
        """Ensures data directory and status file are initialized."""
        if not os.path.exists(self.config.DATA_PATH):
            os.makedirs(self.config.DATA_PATH)
        
        if not os.path.exists(self.config.STATUS_FILE_PATH):
            with open(self.config.STATUS_FILE_PATH, 'w') as f:
                json.dump({'status': 'idle'}, f)
    
    def _register_routes(self):
        """Registers all application routes."""
        # Main routes
        self.app.route('/')(self._index)
        self.app.route('/doc')(self._documentation)
        
        # API routes
        self.app.route('/api/analyze', methods=['POST'])(self._api_analyze)
        self.app.route('/api/status')(self._api_status)
        self.app.route('/api/check-limit')(self._api_check_limit)
        self.app.route('/api/history')(self._logout_required(self._api_get_history))
        self.app.route('/api/history/<int:repo_id>')(self._logout_required(self._api_get_repository_details))
        
        # Authentication routes
        self.app.route('/login', methods=['GET', 'POST'])(self._login)
        self.app.route('/logout')(self._logout_required(self._logout))
        self.app.route('/sign-up', methods=['GET', 'POST'])(self._sign_up)
    
    def _logout_required(self, func):
        """Decorator to require login for logout route."""
        return login_required(func)
    
    # ============ Main Routes ============
    
    def _index(self):
        """Home page route."""
        return render_template('index.html', user=current_user)
    
    def _documentation(self):
        """Documentation viewer route."""
        try:
            with open(self.config.STATUS_FILE_PATH, 'r') as f:
                status = json.load(f)
            
            if status.get('status') == 'completed':
                return render_template('doc.html', data=status.get('result'), user=current_user)
            else:
                return "Analysis not complete. Please wait.", 404
        except (FileNotFoundError, json.JSONDecodeError):
            return "Analysis has not been run yet.", 404
    
    # ============ API Routes ============
    
    def _api_analyze(self):
        """API endpoint to start repository analysis."""
        repo_url = request.json.get('repo_url')
        if not repo_url:
            return jsonify({'error': 'Repository URL is required'}), 400
        
        # Check rate limiting for anonymous users
        if not current_user.is_authenticated:
            session_id = session.get('session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id
            
            count = AnalysisLog.query.filter_by(session_id=session_id).count()
            if count >= self.config.ANONYMOUS_GENERATION_LIMIT:
                return jsonify({
                    'error': 'Generation limit reached',
                    'message': f'You have reached the limit of {self.config.ANONYMOUS_GENERATION_LIMIT} free generations. Please login to continue.',
                    'limit_reached': True
                }), 403
        
        # Check if analysis is already running
        try:
            with open(self.config.STATUS_FILE_PATH, 'r') as f:
                status = json.load(f)
                if status.get('status') == 'processing':
                    return jsonify({'error': 'An analysis is already in progress'}), 409
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        # Log the analysis request
        analysis_log = AnalysisLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session.get('session_id') if not current_user.is_authenticated else None,
            repo_url=repo_url,
            status='pending'
        )
        db.session.add(analysis_log)
        db.session.commit()
        
        # Start worker as subprocess
        subprocess.Popen([sys.executable, 'worker.py', repo_url, str(analysis_log.id)])
        
        return jsonify({'status': 'success', 'message': 'Analysis started'}), 202
    
    def _api_status(self):
        """API endpoint to check analysis status."""
        try:
            with open(self.config.STATUS_FILE_PATH, 'r') as f:
                status = json.load(f)
                return jsonify(status)
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({'status': 'idle', 'result': None, 'error': None})
    
    def _api_check_limit(self):
        """API endpoint to check generation limit for current user/session."""
        if current_user.is_authenticated:
            count = current_user.get_analysis_count()
            return jsonify({
                'can_generate': True,
                'count': count,
                'limit': None,
                'authenticated': True
            })
        else:
            session_id = session.get('session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id
            
            count = AnalysisLog.query.filter_by(session_id=session_id).count()
            limit = self.config.ANONYMOUS_GENERATION_LIMIT
            
            return jsonify({
                'can_generate': count < limit,
                'count': count,
                'limit': limit,
                'authenticated': False
            })
    
    def _api_get_history(self):
        """API endpoint to get user's repository history (requires authentication)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        history = get_user_repository_history(current_user.id, use_cache=True)
        return jsonify({'history': history})
    
    def _api_get_repository_details(self, repo_id):
        """API endpoint to get specific repository details (requires authentication)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        details = get_repository_details(current_user.id, repo_id)
        if not details:
            return jsonify({'error': 'Repository not found'}), 404
        
        return jsonify(details)
    
    # ============ Authentication Routes ============
    
    def _login(self):
        """User login route."""
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            user = User.query.filter_by(email=email).first()
            if user:
                if check_password_hash(user.password, password):
                    flash('Logged in successfully!', category='success')
                    login_user(user, remember=True)
                    return redirect(url_for('_index'))
                else:
                    flash('Incorrect password, try again.', category='error')
            else:
                flash('Email does not exist.', category='error')
        
        return render_template("login.html", user=current_user)
    
    def _logout(self):
        """User logout route."""
        logout_user()
        return redirect(url_for('_index'))
    
    def _sign_up(self):
        """User registration route."""
        if request.method == 'POST':
            email = request.form.get('email')
            first_name = request.form.get('firstName')
            password1 = request.form.get('password1')
            password2 = request.form.get('password2')
            
            user = User.query.filter_by(email=email).first()
            if user:
                flash('Email already exists.', category='error')
            elif len(email) < 4:
                flash('Email must be greater than 3 characters.', category='error')
            elif len(first_name) < 2:
                flash('First name must be greater than 1 character.', category='error')
            elif password1 != password2:
                flash("Passwords don't match.", category='error')
            elif len(password1) < 7:
                flash('Password must be at least 7 characters.', category='error')
            else:
                new_user = User(
                    email=email,
                    first_name=first_name,
                    password=generate_password_hash(password1, method='pbkdf2:sha256')
                )
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user, remember=True)
                flash('Account created successfully!', category='success')
                return redirect(url_for('_index'))
        
        return render_template("sign_up.html", user=current_user)
    
    def run(self, **kwargs):
        """Runs the Flask application."""
        self.app.run(**kwargs)


def create_app():
    """Factory function to create Flask application."""
    archimind = ArchiMindApplication()
    return archimind.app


if __name__ == "__main__":
    archimind = ArchiMindApplication()
    archimind.run(debug=True)
