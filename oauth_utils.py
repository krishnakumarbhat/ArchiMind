"""
OAuth2 and lightweight caching utilities for ArchiMind.
Handles Google OAuth2 authentication and in-process cache for repository history.
"""
import json
import logging
import os
from flask import Blueprint, redirect, url_for, flash
from flask_login import login_user
from authlib.integrations.flask_client import OAuth
from models import User, Repository, RepositoryHistory, AnalysisArtifact, db

logger = logging.getLogger(__name__)

oauth = OAuth()

history_cache = {}


def init_redis():
    """Backward-compatible hook retained as a no-op for lightweight deployments."""
    return


def init_oauth(app):
    """Initialize OAuth with Flask app."""
    oauth.init_app(app)

    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )


oauth_bp = Blueprint('oauth', __name__)


@oauth_bp.route('/login/google')
def google_login():
    redirect_uri = url_for('oauth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@oauth_bp.route('/login/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('_index'))

        user = User.query.filter_by(oauth_id=user_info['sub']).first()

        if not user:
            user = User.query.filter_by(email=user_info['email']).first()
            if user:
                user.oauth_provider = 'google'
                user.oauth_id = user_info['sub']
            else:
                user = User(
                    email=user_info['email'],
                    first_name=user_info.get('given_name', user_info['email'].split('@')[0]),
                    oauth_provider='google',
                    oauth_id=user_info['sub'],
                    password=None,
                )
                db.session.add(user)

            db.session.commit()

        login_user(user, remember=True)
        flash('Logged in successfully with Google!', 'success')
        return redirect(url_for('_index'))

    except Exception as exc:
        logger.error("Google OAuth callback failed: %s", exc)
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('_index'))


def invalidate_history_cache(user_id):
    history_cache.pop(f'user:{user_id}:history', None)


def get_user_repository_history(user_id, use_cache=True):
    cache_key = f'user:{user_id}:history'
    if use_cache:
        cached = history_cache.get(cache_key)
        if cached:
            return cached

    user = db.session.get(User, user_id)
    if not user:
        return []

    entries = user.get_recent_repositories(limit=5)

    history_data = []
    for entry in entries:
        repo = entry.repository
        artifact_types = {a.artifact_type for a in entry.artifacts}
        history_data.append({
            'id': entry.id,
            'repo_name': repo.name if repo else 'Unknown',
            'repo_url': repo.url if repo else '',
            'last_accessed': entry.last_accessed.isoformat(),
            'has_documentation': 'documentation' in artifact_types,
            'has_hld': 'hld_graph' in artifact_types,
            'has_lld': 'lld_graph' in artifact_types,
        })

    if use_cache:
        history_cache[cache_key] = history_data

    return history_data


def save_repository_to_history(user_id, repo_url, repo_name,
                               documentation=None, hld_graph=None,
                               lld_graph=None, chat_summary=None):
    if isinstance(hld_graph, dict):
        hld_graph = json.dumps(hld_graph)
    if isinstance(lld_graph, dict):
        lld_graph = json.dumps(lld_graph)

    RepositoryHistory.add_or_update(
        user_id=user_id,
        repo_url=repo_url,
        repo_name=repo_name,
        documentation=documentation,
        hld_graph=hld_graph,
        lld_graph=lld_graph,
        chat_summary=chat_summary,
    )

    invalidate_history_cache(user_id)


def get_repository_details(user_id, repo_id):
    history = RepositoryHistory.query.filter_by(user_id=user_id, id=repo_id).first()
    if not history:
        return None

    repo = history.repository
    artifacts = {a.artifact_type: a.content for a in history.artifacts}

    hld_raw = artifacts.get('hld_graph')
    lld_raw = artifacts.get('lld_graph')

    return {
        'repo_name': repo.name if repo else 'Unknown',
        'repo_url': repo.url if repo else '',
        'documentation': artifacts.get('documentation'),
        'hld_graph': json.loads(hld_raw) if hld_raw else None,
        'lld_graph': json.loads(lld_raw) if lld_raw else None,
        'last_accessed': history.last_accessed.isoformat(),
    }
