"""ArchiMind Flask application entrypoint and route definitions."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import uuid

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import config
from models import AnalysisLog, Repository, User, db
from oauth_utils import (
    get_repository_details,
    get_user_repository_history,
    init_oauth,
    init_redis,
    oauth_bp,
)
from services import DocumentationService, RepositoryService, VectorStoreService


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _redact_url(url: str) -> str:
    """Replace password segment in a database URL for safe logging."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


def _build_csp_header() -> str:
    directives = {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "https:"],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "data:", "https://fonts.gstatic.com"],
        "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
        "connect-src": [
            "'self'",
            "https://api.github.com",
            "https://raw.githubusercontent.com",
            "https://cdn.jsdelivr.net",
            "https://generativelanguage.googleapis.com",
            "https://*.pinecone.io",
        ],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'", "https://accounts.google.com"],
    }
    return "; ".join(f"{name} {' '.join(values)}" for name, values in directives.items())


class ApplicationConfig:
    """Runtime configuration for the Flask application."""

    def __init__(self):
        debug_enabled = _get_bool_env("FLASK_DEBUG", False)
        default_secure_cookie = not debug_enabled

        self.SECRET_KEY = os.getenv("SECRET_KEY", uuid.uuid4().hex)
        self.DATA_PATH = config.DATA_PATH
        self.STATUS_FILE_PATH = config.STATUS_FILE_PATH
        self.DATABASE_URL = config.get_database_url()
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.ANONYMOUS_GENERATION_LIMIT = config.ANONYMOUS_GENERATION_LIMIT
        self.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
        self.GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
        self.PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")
        self.SESSION_COOKIE_SECURE = _get_bool_env("SESSION_COOKIE_SECURE", default_secure_cookie)
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
        self.REMEMBER_COOKIE_SECURE = self.SESSION_COOKIE_SECURE
        self.REMEMBER_COOKIE_HTTPONLY = True
        self.REMEMBER_COOKIE_SAMESITE = self.SESSION_COOKIE_SAMESITE
        self.MAX_CONTENT_LENGTH = 2 * 1024 * 1024

        logging.getLogger(self.__class__.__name__).info(
            "Configured DATABASE_URL=%s (DATA_PATH=%s)",
            _redact_url(self.DATABASE_URL),
            self.DATA_PATH,
        )


class ArchiMindApplication:
    """Main application class with route handlers."""

    REPOSITORY_URL_PATTERN = re.compile(
        r"^(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?|git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?)$"
    )

    def __init__(self):
        self.app = Flask(__name__)
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
        self.config = ApplicationConfig()
        self.repo_service = RepositoryService()
        self._initialize_data_directory()
        self._configure_application()
        self._initialize_extensions()
        self._register_security_hooks()
        self._register_routes()

    def _configure_application(self):
        """Configures Flask application settings."""
        self.app.config.update(
            SECRET_KEY=self.config.SECRET_KEY,
            SQLALCHEMY_DATABASE_URI=self.config.DATABASE_URL,
            SQLALCHEMY_TRACK_MODIFICATIONS=self.config.SQLALCHEMY_TRACK_MODIFICATIONS,
            SESSION_COOKIE_HTTPONLY=self.config.SESSION_COOKIE_HTTPONLY,
            SESSION_COOKIE_SECURE=self.config.SESSION_COOKIE_SECURE,
            SESSION_COOKIE_SAMESITE=self.config.SESSION_COOKIE_SAMESITE,
            REMEMBER_COOKIE_HTTPONLY=self.config.REMEMBER_COOKIE_HTTPONLY,
            REMEMBER_COOKIE_SECURE=self.config.REMEMBER_COOKIE_SECURE,
            REMEMBER_COOKIE_SAMESITE=self.config.REMEMBER_COOKIE_SAMESITE,
            PREFERRED_URL_SCHEME=self.config.PREFERRED_URL_SCHEME,
            MAX_CONTENT_LENGTH=self.config.MAX_CONTENT_LENGTH,
        )

        if config.uses_sqlite(self.config.DATABASE_URL):
            self.app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}}
        else:
            self.app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }

    def _initialize_extensions(self):
        """Initializes Flask extensions."""
        db.init_app(self.app)
        init_oauth(self.app)
        self.app.register_blueprint(oauth_bp)
        init_redis()

        self.login_manager = LoginManager()
        setattr(self.login_manager, "login_view", "_login")
        self.login_manager.init_app(self.app)

        @self.login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        with self.app.app_context():
            db.create_all()

    def _register_security_hooks(self):
        """Applies HTTP security headers to every response."""

        @self.app.after_request
        def apply_security_headers(response):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            response.headers.setdefault("Content-Security-Policy", _build_csp_header())
            response.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            response.headers.setdefault("Pragma", "no-cache")

            if self.config.SESSION_COOKIE_SECURE:
                response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

            return response

    def _initialize_data_directory(self):
        """Ensures data directory and status file are initialized."""
        os.makedirs(self.config.DATA_PATH, exist_ok=True)

        if not os.path.exists(self.config.STATUS_FILE_PATH):
            with open(self.config.STATUS_FILE_PATH, "w", encoding="utf-8") as handle:
                json.dump({"status": "idle"}, handle)

    def _status_file_for_analysis(self, analysis_id: int) -> str:
        """Returns the filesystem path for a specific analysis status payload."""
        return os.path.join(self.config.DATA_PATH, f"status_{analysis_id}.json")

    def _resolve_actor_context(self):
        """Returns actor context used for analysis ownership and rate limiting."""
        if current_user.is_authenticated:
            return {"user_id": current_user.id, "session_id": None, "authenticated": True}

        session_id = session.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            session["session_id"] = session_id

        return {"user_id": None, "session_id": session_id, "authenticated": False}

    def _extract_repo_name(self, repo_url: str) -> str:
        parsed = self.repo_service._parse_github_repo(repo_url)
        if parsed:
            return parsed[1]
        return repo_url.rstrip("/").split("/")[-1].removesuffix(".git")

    def _extract_repo_collection(self, repo_url: str) -> str:
        return self.repo_service.build_collection_name(repo_url)

    def _is_valid_repository_url(self, repo_url: str) -> bool:
        if not repo_url or len(repo_url) > 400:
            return False
        return bool(self.REPOSITORY_URL_PATTERN.match(repo_url.strip()))

    def _build_documentation_service(self) -> DocumentationService:
        return DocumentationService(
            api_key=config.GEMINI_API_KEY,
            model_name=config.DOCUMENTATION_MODEL,
            chat_model_name=config.CHAT_MODEL,
            thinking_level=config.GEMINI_THINKING_LEVEL,
            api_version=config.GEMINI_API_VERSION,
            context_char_limit=config.DOCUMENTATION_CONTEXT_CHAR_LIMIT,
        )

    def _register_routes(self):
        """Registers all application routes."""
        self.app.route("/")(self._index)
        self.app.route("/doc")(self._documentation)

        self.app.route("/api/analyze", methods=["POST"])(self._api_analyze)
        self.app.route("/api/status")(self._api_status)
        self.app.route("/api/check-limit")(self._api_check_limit)
        self.app.route("/api/preview")(self._api_preview)
        self.app.route("/api/chat", methods=["POST"])(self._api_chat)
        self.app.route("/api/history")(self._logout_required(self._api_get_history))
        self.app.route("/api/history/<int:repo_id>")(self._logout_required(self._api_get_repository_details))

        self.app.route("/login", methods=["GET", "POST"])(self._login)
        self.app.route("/logout")(self._logout_required(self._logout))
        self.app.route("/sign-up", methods=["GET", "POST"])(self._sign_up)

    def _logout_required(self, func):
        return login_required(func)

    def _index(self):
        return render_template(
            "index.html",
            user=current_user,
            anonymous_limit=self.config.ANONYMOUS_GENERATION_LIMIT,
        )

    def _documentation(self):
        analysis_id = request.args.get("analysis_id", type=int)

        if not analysis_id:
            return "Missing analysis_id parameter.", 400

        status_file = self._status_file_for_analysis(analysis_id)
        try:
            with open(status_file, "r", encoding="utf-8") as handle:
                status = json.load(handle)
            if status.get("status") == "completed":
                return render_template("doc.html", data=status.get("result"), user=current_user)
            return "Analysis not complete. Please wait.", 404
        except (FileNotFoundError, json.JSONDecodeError):
            return "Analysis data not found for this request.", 404

    def _api_analyze(self):
        payload = request.get_json(silent=True) or {}
        repo_url = (payload.get("repo_url") or "").strip()

        if not repo_url:
            return jsonify({"error": "Repository URL is required"}), 400
        if not self._is_valid_repository_url(repo_url):
            return jsonify({"error": "Enter a valid public GitHub repository URL."}), 400

        actor = self._resolve_actor_context()
        if not actor["authenticated"]:
            count = AnalysisLog.query.filter_by(session_id=actor["session_id"]).count()
            if count >= self.config.ANONYMOUS_GENERATION_LIMIT:
                return jsonify(
                    {
                        "error": "Generation limit reached",
                        "message": f"You have reached the limit of {self.config.ANONYMOUS_GENERATION_LIMIT} free generations. Please login to continue.",
                        "limit_reached": True,
                    }
                ), 403

        # Dedup: reuse a recent in-progress or completed analysis for the same URL
        recent_query = AnalysisLog.query.filter_by(repo_url=repo_url).filter(
            AnalysisLog.status.in_(["pending", "processing"])
        )
        if actor["authenticated"]:
            recent_query = recent_query.filter_by(user_id=actor["user_id"])
        else:
            recent_query = recent_query.filter_by(session_id=actor["session_id"])
        existing = recent_query.order_by(AnalysisLog.created_at.desc()).first()
        if existing:
            return jsonify(
                {
                    "status": "success",
                    "message": "Analysis already in progress",
                    "analysis_id": existing.id,
                    "status_url": f"/api/status?analysis_id={existing.id}",
                    "doc_url": f"/doc?analysis_id={existing.id}",
                    "repo_name": self._extract_repo_name(repo_url),
                    "reused": True,
                }
            ), 202

        repo_name = self._extract_repo_name(repo_url)
        parsed_repo = self.repo_service._parse_github_repo(repo_url)
        repo_owner = parsed_repo[0] if parsed_repo else "unknown"
        repository = Repository.get_or_create(url=repo_url, name=repo_name, owner=repo_owner)

        analysis_log = AnalysisLog()
        analysis_log.user_id = actor["user_id"]
        analysis_log.session_id = actor["session_id"]
        analysis_log.repository_id = repository.id
        analysis_log.repo_url = repo_url
        analysis_log.status = "pending"
        db.session.add(analysis_log)
        db.session.commit()

        subprocess.Popen(
            [sys.executable, "worker.py", repo_url, str(analysis_log.id)],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            close_fds=True,
        )

        return jsonify(
            {
                "status": "success",
                "message": "Analysis started",
                "analysis_id": analysis_log.id,
                "status_url": f"/api/status?analysis_id={analysis_log.id}",
                "doc_url": f"/doc?analysis_id={analysis_log.id}",
                "repo_name": repo_name,
            }
        ), 202

    def _api_status(self):
        analysis_id = request.args.get("analysis_id", type=int)

        if analysis_id:
            actor = self._resolve_actor_context()
            query = AnalysisLog.query.filter_by(id=analysis_id)

            if actor["authenticated"]:
                query = query.filter_by(user_id=actor["user_id"])
            else:
                query = query.filter_by(session_id=actor["session_id"])

            analysis_log = query.first()
            if not analysis_log:
                return jsonify({"error": "Analysis not found for this user/session."}), 404

            status_file = self._status_file_for_analysis(analysis_id)
            try:
                with open(status_file, "r", encoding="utf-8") as handle:
                    status = json.load(handle)
                return jsonify(status)
            except (FileNotFoundError, json.JSONDecodeError):
                return jsonify(
                    {
                        "status": analysis_log.status,
                        "result": None,
                        "error": None,
                        "analysis_id": analysis_id,
                    }
                )

        return jsonify({"status": "idle", "result": None, "error": None, "analysis_id": None})

    def _api_check_limit(self):
        if current_user.is_authenticated:
            count = current_user.get_analysis_count()
            return jsonify(
                {
                    "can_generate": True,
                    "count": count,
                    "limit": None,
                    "authenticated": True,
                }
            )

        session_id = session.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            session["session_id"] = session_id

        count = AnalysisLog.query.filter_by(session_id=session_id).count()
        limit = self.config.ANONYMOUS_GENERATION_LIMIT
        return jsonify(
            {
                "can_generate": count < limit,
                "count": count,
                "limit": limit,
                "authenticated": False,
            }
        )

    def _api_preview(self):
        repo_url = (request.args.get("repo_url") or "").strip()
        if not self._is_valid_repository_url(repo_url):
            return jsonify({"error": "Enter a valid public GitHub repository URL."}), 400

        preview = self.repo_service.get_repository_preview(repo_url)
        if not preview:
            return jsonify({"error": "Repository preview could not be loaded."}), 404
        return jsonify(preview)

    def _api_chat(self):
        payload = request.get_json(silent=True) or {}
        repo_url = (payload.get("repo_url") or "").strip()
        repo_name = (payload.get("repo_name") or self._extract_repo_name(repo_url)).strip()
        question = (payload.get("question") or "").strip()
        repo_collection = self._extract_repo_collection(repo_url) if repo_url else ""

        if not repo_url or not repo_name:
            return jsonify({"error": "Repository context is required."}), 400
        if not question or len(question) > 600:
            return jsonify({"error": "Ask a concrete question under 600 characters."}), 400

        vector_service = VectorStoreService(
            db_path=config.VECTOR_STORE_PATH,
            collection_name=repo_collection,
            embedding_model=config.EMBEDDING_MODEL,
            repo_url=repo_url,
        )
        if vector_service.is_empty():
            return jsonify({"error": "No index found for this repository. Analyze it first."}), 404

        context = vector_service.query_similar_documents(question, n_results=10)
        if not context:
            return jsonify({"error": "No relevant context was found for that question."}), 404

        documentation_service = self._build_documentation_service()
        answer = documentation_service.generate_chat_answer(context, repo_name, question)
        return jsonify({"answer": answer, "backend": documentation_service.describe_backend()})

    def _api_get_history(self):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401

        history = get_user_repository_history(current_user.id, use_cache=True)
        return jsonify({"history": history})

    def _api_get_repository_details(self, repo_id):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401

        details = get_repository_details(current_user.id, repo_id)
        if not details:
            return jsonify({"error": "Repository not found"}), 404

        return jsonify(details)

    def _login(self):
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            password_value = password or ""

            user = User.query.filter_by(email=email).first()
            if user and user.password and check_password_hash(user.password, password_value):
                flash("Logged in successfully!", category="success")
                login_user(user, remember=True)
                return redirect(url_for("_index"))
            if user:
                flash("Incorrect password, try again.", category="error")
            else:
                flash("Email does not exist.", category="error")

        return render_template("login.html", user=current_user)

    def _logout(self):
        logout_user()
        return redirect(url_for("_index"))

    def _sign_up(self):
        if request.method == "POST":
            email = request.form.get("email")
            first_name = request.form.get("firstName")
            password1 = request.form.get("password1")
            password2 = request.form.get("password2")

            user = User.query.filter_by(email=email).first()
            if user:
                flash("Email already exists.", category="error")
            elif len(email or "") < 4:
                flash("Email must be greater than 3 characters.", category="error")
            elif len(first_name or "") < 2:
                flash("First name must be greater than 1 character.", category="error")
            elif password1 != password2:
                flash("Passwords don't match.", category="error")
            elif len(password1 or "") < 7:
                flash("Password must be at least 7 characters.", category="error")
            else:
                new_user = User()
                new_user.email = email or ""
                new_user.first_name = first_name or ""
                new_user.password = generate_password_hash(password1 or "", method="pbkdf2:sha256")
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user, remember=True)
                flash("Account created successfully!", category="success")
                return redirect(url_for("_index"))

        return render_template("sign_up.html", user=current_user)

    def run(self, **kwargs):
        self.app.run(**kwargs)


def create_app():
    archimind = ArchiMindApplication()
    return archimind.app


if __name__ == "__main__":
    archimind = ArchiMindApplication()
    raw_port = os.getenv("FLASK_PORT", "5000")
    try:
        flask_port = int(raw_port)
    except ValueError:
        flask_port = 5000

    archimind.run(
        debug=os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"},
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=flask_port,
    )
