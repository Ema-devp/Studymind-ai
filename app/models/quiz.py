"""Quiz + question models supporting MCQ, True/False, and Fill-in-the-blank."""
import json
from datetime import datetime

from app import db


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey("pdfs.id"), nullable=False, index=True)

    title = db.Column(db.String(255), default="Quiz")
    quiz_type = db.Column(db.String(20), default="mcq")  # mcq | true_false | fill_blank | mixed
    difficulty = db.Column(db.String(20), default="medium")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    questions = db.relationship("QuizQuestion", backref="quiz", lazy="dynamic", cascade="all, delete-orphan")


class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False, index=True)

    question_type = db.Column(db.String(20), nullable=False)  # mcq | true_false | fill_blank
    question_text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=True)  # JSON list, for MCQ
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=True)

    @property
    def options(self):
        return json.loads(self.options_json) if self.options_json else []

    @options.setter
    def options(self, value):
        self.options_json = json.dumps(value or [])
