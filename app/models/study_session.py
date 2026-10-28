"""Tracks study/Pomodoro sessions for streaks and progress analytics."""
from datetime import datetime

from app import db


class StudySession(db.Model):
    __tablename__ = "study_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey("pdfs.id"), nullable=True)

    session_type = db.Column(db.String(20), default="pomodoro")  # pomodoro | free_study
    duration_minutes = db.Column(db.Integer, default=25)
    completed = db.Column(db.Boolean, default=False)

    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
