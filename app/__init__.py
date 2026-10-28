"""
Application factory for StudyMind AI.

Keeping construction in a factory (rather than a global `app = Flask(...)`)
means we can spin up isolated instances for tests, run multiple configs,
and avoid circular imports between blueprints/extensions/models.
"""
import logging
import os

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from google import genai

from app.config import get_config

# --- Extensions (instantiated here, bound to the app in create_app) ---
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
mail = Mail()


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(get_config(config_name))

    _ensure_directories(app)
    _configure_logging(app)
    _init_gemini(app)

    # --- Bind extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    csrf.init_app(app)
    limiter.init_app(app)
    # Flask-Mail requires SMTP config to actually send; if MAIL_SERVER is
    # blank (default, no setup needed for local dev) email_service.py falls
    # back to logging the message instead of raising.
    mail.init_app(app)

    # --- Models must be imported before blueprints/user_loader use them ---
    from app.models import user, pdf, chunk, chat, message, flashcard, quiz, bookmark, settings, study_session, assistant_message  # noqa

    @login_manager.user_loader
    def load_user(user_id):
        return user.User.query.get(int(user_id))

    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_filters(app)
    _register_request_hooks(app)

    return app


def _init_gemini(app: Flask) -> None:
    """Initialize Google GenAI client and attach to app instance."""
    api_key = app.config.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        app.genai_client = genai.Client(api_key=api_key)
        app.logger.info("Gemini AI client successfully initialized.")
    else:
        app.genai_client = None
        app.logger.warning("GEMINI_API_KEY not found in config/environment. AI features may fail.")


def _ensure_directories(app: Flask) -> None:
    for key in ("UPLOAD_FOLDER", "INDEX_FOLDER", "PROCESSED_DATA_FOLDER"):
        os.makedirs(app.config[key], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    app.logger.setLevel(level)


def _register_blueprints(app: Flask) -> None:
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.pdf import pdf_bp
    from app.routes.chat import chat_bp
    from app.routes.ai_features import ai_bp
    from app.routes.search import search_bp
    from app.routes.settings import settings_bp
    from app.routes.api import api_bp
    from app.routes.assistant import assistant_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(assistant_bp)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error: %s", e)
        return render_template("errors/500.html"), 500


def _register_template_filters(app: Flask) -> None:
    from app.utils.helpers import format_filesize, format_datetime, time_ago

    app.jinja_env.filters["filesize"] = format_filesize
    app.jinja_env.filters["datetime"] = format_datetime
    app.jinja_env.filters["time_ago"] = time_ago


# Endpoints an unverified-but-somehow-authenticated user is still allowed to
# hit - everything else redirects them to login. This is a defense-in-depth
# safety net (the login route itself already refuses to authenticate
# unverified accounts) that also catches sessions created before email
# verification became mandatory.
_VERIFICATION_EXEMPT_ENDPOINTS = {
    "auth.login", "auth.register", "auth.logout", "auth.verify_email",
    "auth.resend_verification", "auth.resend_verification_public",
    "auth.forgot_password", "auth.reset_password",
    "static",
}


def _register_request_hooks(app: Flask) -> None:
    @app.before_request
    def enforce_email_verification():
        if not current_user.is_authenticated:
            return None
        if current_user.is_email_verified:
            return None
        if request.endpoint in _VERIFICATION_EXEMPT_ENDPOINTS:
            return None
        logout_user()
        flash("Please verify your email before continuing - check your inbox for the verification link.", "error")
        return redirect(url_for("auth.login"))