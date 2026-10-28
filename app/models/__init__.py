"""
Model package. Importing this package (as done in app/__init__.py) registers
every SQLAlchemy model with the metadata so `db.create_all()` / migrations
pick them all up.
"""
from app.models.user import User
from app.models.pdf import PDF, ProcessingStatus
from app.models.chunk import Chunk
from app.models.chat import Chat
from app.models.message import Message
from app.models.flashcard import FlashcardSet, Flashcard
from app.models.quiz import Quiz, QuizQuestion
from app.models.bookmark import Bookmark
from app.models.settings import UserSettings
from app.models.study_session import StudySession
from app.models.assistant_message import AssistantMessage

__all__ = [
    "User", "PDF", "ProcessingStatus", "Chunk", "Chat", "Message",
    "FlashcardSet", "Flashcard", "Quiz", "QuizQuestion", "Bookmark",
    "UserSettings", "StudySession", "AssistantMessage",
]
