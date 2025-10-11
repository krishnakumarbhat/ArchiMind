# main.py
"""
Main script to run the RAG-based documentation generation workflow.
"""
import logging
import subprocess
import json
import os
import sys
import uuid
from flask import Flask, render_template, request, jsonify, session
from flask_login import LoginManager, login_required, current_user

# Import configurations and managers
import config
import repo_manager
from vector_manager import VectorManager
from doc_generator import DocGenerator
from models import db, User, AnalysisLog
from auth import auth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://localhost/archimind'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Register authentication blueprint
app.register_blueprint(auth, url_prefix='/')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html', user=current_user)

@app.route('/api/analyze', methods=['POST'])
def analyze_repo():
    repo_url = request.json.get('repo_url')
    if not repo_url:
        return jsonify({'error': 'Repository URL is required'}), 400

    # Check rate limiting for anonymous users
    if not current_user.is_authenticated:
        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
        
        # Count anonymous generations
        count = AnalysisLog.query.filter_by(session_id=session_id).count()
        if count >= 5:
            return jsonify({
                'error': 'Generation limit reached',
                'message': 'You have reached the limit of 5 free generations. Please login to continue.',
                'limit_reached': True
            }), 403

    # Check if a process is already running
    try:
        with open(config.STATUS_FILE_PATH, 'r') as f:
            status = json.load(f)
            if status.get('status') == 'processing':
                return jsonify({'error': 'An analysis is already in progress'}), 409
    except (FileNotFoundError, json.JSONDecodeError):
        pass # No status file or it's invalid, so we can proceed

    # Log the analysis request
    analysis_log = AnalysisLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        session_id=session.get('session_id') if not current_user.is_authenticated else None,
        repo_url=repo_url,
        status='pending'
    )
    db.session.add(analysis_log)
    db.session.commit()

    # Start the worker as a separate process
    subprocess.Popen([sys.executable, 'worker.py', repo_url, str(analysis_log.id)])
    
    return jsonify({'status': 'success', 'message': 'Analysis started'}), 202

@app.route('/api/status')
def get_status():
    try:
        with open(config.STATUS_FILE_PATH, 'r') as f:
            status = json.load(f)
            return jsonify(status)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'status': 'idle', 'result': None, 'error': None})

@app.route('/doc')
def documentation():
    try:
        with open(config.STATUS_FILE_PATH, 'r') as f:
            status = json.load(f)
        if status.get('status') == 'completed':
            return render_template('doc.html', data=status.get('result'), user=current_user)
        else:
            return "Analysis not complete or failed. Please check the status.", 404
    except (FileNotFoundError, json.JSONDecodeError):
        return "Analysis has not been run yet.", 404

if __name__ == "__main__":
    # Ensure the data directory and status file are initialized
    if not os.path.exists(config.DATA_PATH):
        os.makedirs(config.DATA_PATH)
    with open(config.STATUS_FILE_PATH, 'w') as f:
        json.dump({'status': 'idle'}, f)

    app.run(debug=True)