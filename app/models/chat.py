"""Chat (conversation) model. A chat belongs to a user and a PDF."""
from datetime import datetime

from app import db


class Chat(db.Model):
    __tablename__ = "chats"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey("pdfs.id"), nullable=False, index=True)

    title = db.Column(db.String(255), default="New Conversation")
    is_pinned = db.Column(db.Boolean, default=False)
    is_favorite = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = db.relationship(
        "Message", backref="chat", lazy="dynamic",
        cascade="all, delete-orphan", order_by="Message.created_at",
    )

    def __repr__(self):
        return f"<Chat {self.id} '{self.title}'>"
