"""
OAuth2 and Redis caching utilities for ArchiMind.
Handles Google OAuth2 authentication with 2FA support and Redis caching for repository history.
"""
import os
import json
import redis
from functools import wraps
from flask import Blueprint, redirect, url_for, session, request, flash
from flask_login import login_user, current_user
from authlib.integrations.flask_client import OAuth
from models import User, db, RepositoryHistory

# Initialize OAuth
oauth = OAuth()

# Initialize Redis client
redis_client = None

def init_redis():
    """Initialize Redis connection."""
    global redis_client
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        print(f"Redis connected successfully at {redis_url}")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        redis_client = None

def init_oauth(app):
    """Initialize OAuth with Flask app."""
    oauth.init_app(app)
    
    # Configure Google OAuth2
    google = oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile',
            # Google automatically handles 2FA if it's enabled on the account
        }
    )
    
    return google

# Create OAuth Blueprint
oauth_bp = Blueprint('oauth', __name__)

@oauth_bp.route('/login/google')
def google_login():
    """Initiate Google OAuth2 login flow."""
    redirect_uri = url_for('oauth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@oauth_bp.route('/login/google/callback')
def google_callback():
    """Handle Google OAuth2 callback."""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('_index'))
        
        # Check if user exists
        user = User.query.filter_by(oauth_id=user_info['sub']).first()
        
        if not user:
            # Check if email already exists (might be regular account)
            user = User.query.filter_by(email=user_info['email']).first()
            if user:
                # Link OAuth to existing account
                user.oauth_provider = 'google'
                user.oauth_id = user_info['sub']
            else:
                # Create new user with OAuth
                user = User(
                    email=user_info['email'],
                    first_name=user_info.get('given_name', user_info['email'].split('@')[0]),
                    oauth_provider='google',
                    oauth_id=user_info['sub'],
                    password=None  # No password for OAuth users
                )
                db.session.add(user)
            
            db.session.commit()
        
        # Log in the user
        login_user(user, remember=True)
        flash('Logged in successfully with Google!', 'success')
        return redirect(url_for('_index'))
        
    except Exception as e:
        flash(f'Authentication failed: {str(e)}', 'error')
        return redirect(url_for('_index'))


# ============ Redis Caching Functions ============

def get_cached_history(user_id):
    """Retrieve cached repository history from Redis."""
    if not redis_client:
        return None
    
    try:
        cache_key = f'user:{user_id}:history'
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        print(f"Redis get error: {e}")
    
    return None

def set_cached_history(user_id, history_data, expiry=3600):
    """Cache repository history in Redis with expiry (default 1 hour)."""
    if not redis_client:
        return False
    
    try:
        cache_key = f'user:{user_id}:history'
        redis_client.setex(cache_key, expiry, json.dumps(history_data))
        return True
    except Exception as e:
        print(f"Redis set error: {e}")
        return False

def invalidate_history_cache(user_id):
    """Invalidate cached history when new repository is added."""
    if not redis_client:
        return False
    
    try:
        cache_key = f'user:{user_id}:history'
        redis_client.delete(cache_key)
        return True
    except Exception as e:
        print(f"Redis delete error: {e}")
        return False

def get_user_repository_history(user_id, use_cache=True):
    """
    Get user's repository history with Redis caching.
    
    Args:
        user_id: User's database ID
        use_cache: Whether to use Redis cache (default True)
    
    Returns:
        List of repository history dictionaries
    """
    # Try cache first
    if use_cache:
        cached = get_cached_history(user_id)
        if cached:
            return cached
    
    # Fetch from database
    user = User.query.get(user_id)
    if not user:
        return []
    
    repositories = user.get_recent_repositories(limit=5)
    
    # Format data
    history_data = [
        {
            'id': repo.id,
            'repo_name': repo.repo_name,
            'repo_url': repo.repo_url,
            'last_accessed': repo.last_accessed.isoformat(),
            'has_documentation': repo.documentation is not None,
            'has_hld': repo.hld_graph is not None,
            'has_lld': repo.lld_graph is not None
        }
        for repo in repositories
    ]
    
    # Cache the result
    if use_cache:
        set_cached_history(user_id, history_data)
    
    return history_data

def save_repository_to_history(user_id, repo_url, repo_name, documentation=None, hld_graph=None, lld_graph=None, chat_summary=None):
    """
    Save or update repository in user's history and invalidate cache.
    
    Args:
        user_id: User's database ID
        repo_url: Repository URL
        repo_name: Repository name
        documentation: Gemini-generated documentation (optional)
        hld_graph: HLD graph JSON (optional)
        lld_graph: LLD graph JSON (optional)
    """
    # Convert JSON objects to strings if needed
    if isinstance(hld_graph, dict):
        hld_graph = json.dumps(hld_graph)
    if isinstance(lld_graph, dict):
        lld_graph = json.dumps(lld_graph)
    
    # Save to database
    RepositoryHistory.add_or_update(
        user_id=user_id,
        repo_url=repo_url,
        repo_name=repo_name,
        documentation=documentation,
        hld_graph=hld_graph,
        lld_graph=lld_graph,
        chat_summary=chat_summary
    )
    
    # Invalidate cache
    invalidate_history_cache(user_id)

def get_repository_details(user_id, repo_id):
    """Get full repository details including Gemini outputs."""
    history = RepositoryHistory.query.filter_by(
        user_id=user_id, 
        id=repo_id
    ).first()
    
    if not history:
        return None
    
    return {
        'repo_name': history.repo_name,
        'repo_url': history.repo_url,
        'documentation': history.documentation,
        'hld_graph': json.loads(history.hld_graph) if history.hld_graph else None,
        'lld_graph': json.loads(history.lld_graph) if history.lld_graph else None,
        'last_accessed': history.last_accessed.isoformat()
    }
