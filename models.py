"""Database models for ArchiMind — 5NF-normalized schema for Supabase PostgreSQL."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime

db = SQLAlchemy()


class Repository(db.Model):
    """Canonical repository record (eliminates URL/name duplication across tables)."""
    __tablename__ = 'repositories'

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    owner = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    analyses = db.relationship('AnalysisLog', backref='repository', lazy=True)
    history_entries = db.relationship('RepositoryHistory', backref='repository', lazy=True)

    def __repr__(self):
        return f'<Repository {self.owner}/{self.name}>'

    @classmethod
    def get_or_create(cls, url: str, name: str, owner: str) -> 'Repository':
        """Return an existing Repository or create a new one."""
        existing = cls.query.filter_by(url=url).first()
        if existing:
            return existing
        repo = cls(url=url, name=name, owner=owner)
        db.session.add(repo)
        db.session.flush()
        return repo


class User(db.Model, UserMixin):
    """User model for authentication."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(150), nullable=False)
    oauth_provider = db.Column(db.String(50), nullable=True)
    oauth_id = db.Column(db.String(255), nullable=True, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    analyses = db.relationship('AnalysisLog', backref='user', lazy=True, cascade='all, delete-orphan')
    repository_history = db.relationship(
        'RepositoryHistory', backref='user', lazy=True,
        cascade='all, delete-orphan', order_by='RepositoryHistory.last_accessed.desc()',
    )

    def __repr__(self):
        return f'<User {self.email}>'

    def get_analysis_count(self):
        return len(self.analyses)

    def get_recent_repositories(self, limit=5):
        return (
            RepositoryHistory.query
            .filter_by(user_id=self.id)
            .order_by(RepositoryHistory.last_accessed.desc())
            .limit(limit)
            .all()
        )


class AnalysisLog(db.Model):
    """Tracks repository analysis requests for rate limiting."""
    __tablename__ = 'analysis_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    session_id = db.Column(db.String(255), nullable=True, index=True)
    repository_id = db.Column(db.Integer, db.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=True, index=True)
    repo_url = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f'<AnalysisLog {self.repo_url} - {self.status}>'


class RepositoryHistory(db.Model):
    """Join entity linking a user to a repository with access timestamp."""
    __tablename__ = 'repository_history'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'repository_id', name='uq_user_repository'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    repository_id = db.Column(db.Integer, db.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False, index=True)
    last_accessed = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    artifacts = db.relationship('AnalysisArtifact', backref='history', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<RepositoryHistory user={self.user_id} repo={self.repository_id}>'

    @classmethod
    def add_or_update(cls, user_id, repo_url, repo_name, documentation=None,
                      hld_graph=None, lld_graph=None, chat_summary=None):
        """Add or update history entry and its artifacts, keeping top 5 per user."""
        import re
        owner_match = re.search(r'github\.com[:/]([^/]+)/', repo_url)
        owner = owner_match.group(1) if owner_match else 'unknown'
        repo = Repository.get_or_create(url=repo_url, name=repo_name, owner=owner)

        existing = cls.query.filter_by(user_id=user_id, repository_id=repo.id).first()

        if existing:
            existing.last_accessed = datetime.utcnow()
            history = existing
        else:
            history = cls(user_id=user_id, repository_id=repo.id)
            db.session.add(history)
            db.session.flush()

            count = cls.query.filter_by(user_id=user_id).count()
            if count > 5:
                oldest = (
                    cls.query.filter_by(user_id=user_id)
                    .order_by(cls.last_accessed.asc())
                    .first()
                )
                if oldest and oldest.id != history.id:
                    db.session.delete(oldest)

        artifact_map = {
            'documentation': documentation,
            'hld_graph': hld_graph,
            'lld_graph': lld_graph,
            'chat_summary': chat_summary,
        }
        for artifact_type, content in artifact_map.items():
            if content is None:
                continue
            content_str = content if isinstance(content, str) else __import__('json').dumps(content)
            art = AnalysisArtifact.query.filter_by(
                history_id=history.id, artifact_type=artifact_type,
            ).first()
            if art:
                art.content = content_str
            else:
                db.session.add(AnalysisArtifact(
                    history_id=history.id,
                    artifact_type=artifact_type,
                    content=content_str,
                ))

        db.session.commit()


class AnalysisArtifact(db.Model):
    """Normalized artifact storage — one row per artifact type per history entry."""
    __tablename__ = 'analysis_artifacts'
    __table_args__ = (
        db.UniqueConstraint('history_id', 'artifact_type', name='uq_history_artifact'),
    )

    id = db.Column(db.Integer, primary_key=True)
    history_id = db.Column(db.Integer, db.ForeignKey('repository_history.id', ondelete='CASCADE'), nullable=False, index=True)
    artifact_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
