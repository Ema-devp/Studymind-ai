"""Per-user application preferences."""
from app import db


class UserSettings(db.Model):
    __tablename__ = "user_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    theme = db.Column(db.String(10), default="dark")  # dark | light
    language = db.Column(db.String(10), default="en")

    ai_temperature = db.Column(db.Float, default=0.4)
    chunk_size = db.Column(db.Integer, default=800)
    chunk_overlap = db.Column(db.Integer, default=120)
    top_k = db.Column(db.Integer, default=5)

    daily_goal_minutes = db.Column(db.Integer, default=30)
    email_notifications = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "theme": self.theme,
            "language": self.language,
            "ai_temperature": self.ai_temperature,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "top_k": self.top_k,
            "daily_goal_minutes": self.daily_goal_minutes,
            "email_notifications": self.email_notifications,
        }
