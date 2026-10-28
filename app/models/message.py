"""Individual chat messages, including the dual-answer (PDF vs AI) payload."""
import json
from datetime import datetime

from app import db


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=False, index=True)

    role = db.Column(db.String(20), nullable=False)  # 'user' | 'assistant'
    content = db.Column(db.Text, nullable=False)  # for user: the question; for assistant: fallback/plain text

    # --- Dual Answer Mode (assistant messages only) ---
    pdf_answer = db.Column(db.Text, nullable=True)
    ai_explanation = db.Column(db.Text, nullable=True)
    sources_json = db.Column(db.Text, nullable=True)  # JSON list of {pdf_id, page, snippet, score}
    confidence_score = db.Column(db.Float, nullable=True)  # 0-1

    is_edited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def sources(self):
        if not self.sources_json:
            return []
        return json.loads(self.sources_json)

    @sources.setter
    def sources(self, value):
        self.sources_json = json.dumps(value or [])

    def __repr__(self):
        return f"<Message {self.id} role={self.role}>"
