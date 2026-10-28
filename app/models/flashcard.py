"""Flashcard set + individual flashcards."""
from datetime import datetime

from app import db


class FlashcardSet(db.Model):
    __tablename__ = "flashcard_sets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey("pdfs.id"), nullable=False, index=True)

    title = db.Column(db.String(255), default="Flashcards")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    cards = db.relationship("Flashcard", backref="flashcard_set", lazy="dynamic", cascade="all, delete-orphan")


class Flashcard(db.Model):
    __tablename__ = "flashcards"

    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey("flashcard_sets.id"), nullable=False, index=True)

    front = db.Column(db.Text, nullable=False)
    back = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), default="medium")  # easy | medium | hard
    times_reviewed = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
