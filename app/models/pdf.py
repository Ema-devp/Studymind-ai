"""Uploaded PDF document model."""
from datetime import datetime
import enum

from app import db


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PDF(db.Model):
    __tablename__ = "pdfs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    title = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_path = db.Column(db.String(512), nullable=False)

    page_count = db.Column(db.Integer, default=0)
    file_size_bytes = db.Column(db.Integer, default=0)
    chunk_count = db.Column(db.Integer, default=0)

    processing_status = db.Column(db.Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)
    processing_error = db.Column(db.Text, nullable=True)

    index_path = db.Column(db.String(512), nullable=True)  # FAISS index file
    metadata_path = db.Column(db.String(512), nullable=True)  # chunk metadata json

    is_favorite = db.Column(db.Boolean, default=False)
    topics = db.Column(db.Text, nullable=True)  # comma-separated auto-extracted topics
    keywords = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = db.relationship("Chunk", backref="pdf", lazy="dynamic", cascade="all, delete-orphan")
    chats = db.relationship("Chat", backref="pdf", lazy="dynamic", cascade="all, delete-orphan")
    flashcard_sets = db.relationship("FlashcardSet", backref="pdf", lazy="dynamic", cascade="all, delete-orphan")
    quizzes = db.relationship("Quiz", backref="pdf", lazy="dynamic", cascade="all, delete-orphan")
    bookmarks = db.relationship("Bookmark", backref="pdf", lazy="dynamic", cascade="all, delete-orphan")

    def topics_list(self):
        return [t.strip() for t in (self.topics or "").split(",") if t.strip()]

    def __repr__(self):
        return f"<PDF {self.title} ({self.processing_status})>"
