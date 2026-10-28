"""Bookmarks let a user save a specific chunk/answer of a PDF for later review."""
from datetime import datetime

from app import db


class Bookmark(db.Model):
    __tablename__ = "bookmarks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey("pdfs.id"), nullable=False, index=True)

    note = db.Column(db.Text, nullable=True)
    page_number = db.Column(db.Integer, nullable=True)
    excerpt = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
