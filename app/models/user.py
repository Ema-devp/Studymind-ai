"""User account model."""
import secrets
from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)

    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verify_token = db.Column(db.String(64), nullable=True)
    reset_password_token = db.Column(db.String(64), nullable=True)
    reset_password_expires = db.Column(db.DateTime, nullable=True)

    study_streak = db.Column(db.Integer, default=0, nullable=False)
    last_active_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Relationships ---
    pdfs = db.relationship("PDF", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    chats = db.relationship("Chat", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    flashcard_sets = db.relationship("FlashcardSet", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    quizzes = db.relationship("Quiz", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    bookmarks = db.relationship("Bookmark", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    settings = db.relationship("UserSettings", backref="owner", uselist=False, cascade="all, delete-orphan")
    study_sessions = db.relationship("StudySession", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    assistant_messages = db.relationship("AssistantMessage", backref="owner", lazy="dynamic", cascade="all, delete-orphan")

    # --- Password helpers ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # --- Token helpers ---
    def generate_email_verify_token(self) -> str:
        self.email_verify_token = secrets.token_urlsafe(32)
        return self.email_verify_token

    def generate_reset_token(self, expires_in_minutes: int = 30) -> str:
        self.reset_password_token = secrets.token_urlsafe(32)
        self.reset_password_expires = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        return self.reset_password_token

    def reset_token_valid(self, token: str) -> bool:
        return (
            self.reset_password_token == token
            and self.reset_password_expires is not None
            and self.reset_password_expires > datetime.utcnow()
        )

    def clear_reset_token(self) -> None:
        self.reset_password_token = None
        self.reset_password_expires = None

    # --- Study streak ---
    def register_activity(self) -> None:
        """Call whenever the user does something study-related, to update streak."""
        today = datetime.utcnow().date()
        if self.last_active_date == today:
            return
        if self.last_active_date == today - timedelta(days=1):
            self.study_streak += 1
        else:
            self.study_streak = 1
        self.last_active_date = today

    def __repr__(self):
        return f"<User {self.email}>"
