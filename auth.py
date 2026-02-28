"""
Authentication routes for ArchiMind.
Handles user login, signup, and logout functionality.
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from models import User, db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """User login page and handler."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                flash('Logged in successfully!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('index'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Email does not exist.', category='error')

    return render_template("login.html", user=current_user)


@auth.route('/logout')
@login_required
def logout():
    """Logout current user."""
    logout_user()
    return redirect(url_for('index'))


@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    """User registration page and handler."""
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
            # Create new user with hashed password
            new_user = User(
                email=email,
                first_name=first_name,
                password=generate_password_hash(password1, method='pbkdf2:sha256')
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('Account created successfully!', category='success')
            return redirect(url_for('index'))

    return render_template("sign_up.html", user=current_user)


@auth.route('/api/check-limit', methods=['GET'])
def check_limit():
    """
    API endpoint to check if user has reached generation limit.
    Returns:
        - can_generate: boolean
        - count: current count
        - limit: max allowed for anonymous users
    """
    from models import AnalysisLog
    from flask import session
    
    if current_user.is_authenticated:
        # Logged-in users have unlimited access
        count = current_user.get_analysis_count()
        return jsonify({
            'can_generate': True,
            'count': count,
            'limit': None,
            'authenticated': True
        })
    else:
        # Anonymous users limited to 5 generations
        session_id = session.get('session_id')
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
        
        count = AnalysisLog.query.filter_by(session_id=session_id).count()
        limit = 5
        
        return jsonify({
            'can_generate': count < limit,
            'count': count,
            'limit': limit,
            'authenticated': False
        })
