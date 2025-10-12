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
    password = db.Column(db.String(255), nullable=True)  # Nullable for OAuth users
    first_name = db.Column(db.String(150), nullable=False)
    oauth_provider = db.Column(db.String(50), nullable=True)  # 'google', etc.
    oauth_id = db.Column(db.String(255), nullable=True, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analyses = db.relationship('AnalysisLog', backref='user', lazy=True, cascade='all, delete-orphan')
    repository_history = db.relationship('RepositoryHistory', backref='user', lazy=True, 
                                        cascade='all, delete-orphan', order_by='RepositoryHistory.last_accessed.desc()')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def get_analysis_count(self):
        """Returns the total number of analyses performed by this user."""
        return len(self.analyses)
    
    def get_recent_repositories(self, limit=5):
        """Returns the most recent repositories analyzed by this user."""
        return RepositoryHistory.query.filter_by(user_id=self.id)\
            .order_by(RepositoryHistory.last_accessed.desc()).limit(limit).all()


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


class RepositoryHistory(db.Model):
    """Stores top 5 most recent repository analyses per user with Gemini outputs."""
    __tablename__ = 'repository_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    repo_url = db.Column(db.String(500), nullable=False)
    repo_name = db.Column(db.String(255), nullable=False)
    documentation = db.Column(db.Text, nullable=True)  # Gemini-generated documentation
    hld_graph = db.Column(db.Text, nullable=True)  # HLD JSON
    lld_graph = db.Column(db.Text, nullable=True)  # LLD JSON
    chat_summary = db.Column(db.Text, nullable=True)  # Chat summary using Gemini Flash
    last_accessed = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f'<RepositoryHistory {self.repo_name} - User {self.user_id}>'
    
    @classmethod
    def add_or_update(cls, user_id, repo_url, repo_name, documentation=None, hld_graph=None, lld_graph=None, chat_summary=None):
        """Add or update repository history, maintaining top 5 limit per user."""
        # Check if repository already exists for this user
        existing = cls.query.filter_by(user_id=user_id, repo_url=repo_url).first()
        
        if existing:
            # Update existing record
            existing.documentation = documentation
            existing.hld_graph = hld_graph
            existing.lld_graph = lld_graph
            existing.chat_summary = chat_summary
            existing.last_accessed = datetime.utcnow()
        else:
            # Create new record
            new_history = cls(
                user_id=user_id,
                repo_url=repo_url,
                repo_name=repo_name,
                documentation=documentation,
                hld_graph=hld_graph,
                lld_graph=lld_graph,
                chat_summary=chat_summary
            )
            db.session.add(new_history)
            
            # Maintain only top 5 repositories per user
            count = cls.query.filter_by(user_id=user_id).count()
            if count >= 5:
                # Delete oldest entry
                oldest = cls.query.filter_by(user_id=user_id)\
                    .order_by(cls.last_accessed.asc()).first()
                if oldest:
                    db.session.delete(oldest)
        
        db.session.commit()
