"""
Application configuration.

Loads settings from environment variables (see .env.example) and exposes a
small hierarchy of config classes so the app can be pointed at SQLite in
development and swapped to Postgres (or anything SQLAlchemy supports) in
production without touching code elsewhere.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# Load .env explicitly, here, rather than relying on it happening implicitly.
# `flask run` auto-loads .env via python-dotenv, but `python run.py` and
# `gunicorn run:app` do not - without this line, anything only set in .env
# (and not as a real OS environment variable) is silently ignored, which is
# exactly what makes MAIL_SERVER/MAIL_USERNAME/etc. look "unconfigured" even
# after filling them in. override=False means real OS env vars (e.g. ones
# set in a deployment platform's dashboard) still win over .env if both exist.
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)


def env_str(name: str, default: str) -> str:
    """Like os.environ.get, but treats a blank value ('') the same as unset.
    This matters because a line like `DATABASE_URL=` in a .env file sets the
    variable to an empty string rather than leaving it undefined."""
    value = os.environ.get(name)
    return value if value else default


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


class Config:
    """Base configuration shared by all environments."""

    # --- Core Flask ---
    SECRET_KEY = env_str("SECRET_KEY", "dev-secret-key-change-me")
    WTF_CSRF_ENABLED = True
    JSON_SORT_KEYS = False

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = env_str(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'studymind.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Auth / sessions ---
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- File uploads ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    INDEX_FOLDER = os.path.join(BASE_DIR, "indexes")
    PROCESSED_DATA_FOLDER = os.path.join(BASE_DIR, "processed_data")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB per upload
    ALLOWED_EXTENSIONS = {"pdf"}

    # --- AI Provider selection ---
    # "auto" (default) picks the first provider - in order gemini, openai,
    # anthropic - that has an API key set below. Set this explicitly only if
    # you have more than one key configured and want to pick which is used.
    AI_PROVIDER = env_str("AI_PROVIDER", "auto")
    EMBEDDING_PROVIDER = env_str("EMBEDDING_PROVIDER", "auto")  # anthropic has no embeddings API

    # --- Gemini ---
    GEMINI_API_KEY = env_str("GEMINI_API_KEY", "")
    # `gemini-flash-latest` is Google's "latest" alias: it always points to
    # the current stable Flash model and gives 2 weeks' notice by email
    # before the underlying model changes. Pinning to a dated model string
    # (e.g. gemini-2.0-flash) will eventually break when Google deprecates
    # it - see https://ai.google.dev/gemini-api/docs/models#model-version-name-patterns
    GEMINI_CHAT_MODEL = env_str("GEMINI_CHAT_MODEL", "gemini-flash-latest")
    GEMINI_EMBEDDING_MODEL = env_str("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

    # --- OpenAI ---
    OPENAI_API_KEY = env_str("OPENAI_API_KEY", "")
    OPENAI_CHAT_MODEL = env_str("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL = env_str("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # --- Anthropic (Claude) --- chat only; no embeddings API
    ANTHROPIC_API_KEY = env_str("ANTHROPIC_API_KEY", "")
    ANTHROPIC_CHAT_MODEL = env_str("ANTHROPIC_CHAT_MODEL", "claude-haiku-4-5-20251001")

    # Embedding vector size stored in FAISS. Must match whatever embedding
    # provider/model is actually active - changing providers/models requires
    # reprocessing existing PDFs since old indexes were built at the old
    # dimension. Gemini's embedding-001 defaults to 768; OpenAI's
    # text-embedding-3-small is 1536. Override explicitly if you change models.
    EMBEDDING_DIMENSIONS = env_int("EMBEDDING_DIMENSIONS", 768)

    DEFAULT_CHUNK_SIZE = env_int("DEFAULT_CHUNK_SIZE", 800)
    DEFAULT_CHUNK_OVERLAP = env_int("DEFAULT_CHUNK_OVERLAP", 120)
    DEFAULT_TOP_K = env_int("DEFAULT_TOP_K", 5)
    DEFAULT_AI_TEMPERATURE = env_float("DEFAULT_AI_TEMPERATURE", 0.4)

    # --- Email (verification / password reset) ---
    # If MAIL_SERVER is left blank, emails are logged to the console instead
    # of sent (handy for local dev with no SMTP account). Set these to a real
    # provider (Gmail SMTP, SendGrid, Mailgun, SES, etc.) to send real email.
    MAIL_SERVER = env_str("MAIL_SERVER", "")
    MAIL_PORT = env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = env_str("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USERNAME = env_str("MAIL_USERNAME", "")
    MAIL_PASSWORD = env_str("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = env_str("MAIL_DEFAULT_SENDER", "StudyMind AI <no-reply@studymind.local>")

    # --- Rate limiting ---
    RATELIMIT_DEFAULT = env_str("RATELIMIT_DEFAULT", "200 per hour")
    RATELIMIT_STORAGE_URI = env_str("RATELIMIT_STORAGE_URI", "memory://")

    # --- Pagination ---
    PDFS_PER_PAGE = 12
    CHATS_PER_PAGE = 20
    ASSISTANT_HISTORY_LIMIT = 50


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    # In production, set DATABASE_URL to a Postgres URI, e.g.
    # postgresql+psycopg2://user:password@host:5432/studymind


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None):
    name = name or os.environ.get("FLASK_ENV", "development")
    return config_by_name.get(name, DevelopmentConfig)
