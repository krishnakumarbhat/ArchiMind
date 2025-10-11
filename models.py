"""
Database models for ArchiMind.
Uses PostgreSQL for production-grade authentication and rate limiting.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime

db = SQLAlchemy()


class User(db.Model, UserMixin):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Relationship to analysis logs
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
    session_id = db.Column(db.String(255), nullable=True, index=True)  # For anonymous users
    repo_url = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, completed, failed
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f'<AnalysisLog {self.repo_url} - {self.status}>'
