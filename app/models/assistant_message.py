"""Chat history for the sitewide 'Ask StudyMind' assistant widget.

Unlike Chat/Message (which are tied to a specific PDF and use Dual Answer
Mode), this is a single flat, ungrounded conversation per user - a general
helper for questions about using the app, study strategies, or anything
else, the same way a chat widget in the corner of any AI product works.
"""
from datetime import datetime

from app import db


class AssistantMessage(db.Model):
    __tablename__ = "assistant_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    role = db.Column(db.String(20), nullable=False)  # 'user' | 'assistant'
    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AssistantMessage {self.id} role={self.role}>"
