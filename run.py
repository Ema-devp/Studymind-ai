"""
Entry point for running StudyMind AI locally.

    python run.py

For production, use a WSGI server instead, e.g.:

    gunicorn "run:app" --workers 3 --bind 0.0.0.0:8000
"""
import os

from app import create_app, db

app = create_app(os.environ.get("FLASK_ENV", "development"))


@app.shell_context_processor
def make_shell_context():
    """Lets `flask shell` auto-import common objects."""
    from app.models.user import User
    from app.models.pdf import PDF
    from app.models.chunk import Chunk
    from app.models.chat import Chat
    from app.models.message import Message
    from app.models.flashcard import Flashcard, FlashcardSet
    from app.models.quiz import Quiz, QuizQuestion

    return dict(
        db=db,
        User=User,
        PDF=PDF,
        Chunk=Chunk,
        Chat=Chat,
        Message=Message,
        FlashcardSet=FlashcardSet,
        Flashcard=Flashcard,
        Quiz=Quiz,
        QuizQuestion=QuizQuestion,
    )


@app.cli.command("init-db")
def init_db():
    """Create all database tables (quick-start alternative to Alembic migrations)."""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully.")


@app.cli.command("prune-empty-chats")
def prune_empty_chats():
    """Deletes conversations with zero messages."""
    with app.app_context():
        from app.models.chat import Chat

        empty_chats = [c for c in Chat.query.all() if len(c.messages) == 0]
        count = len(empty_chats)
        for chat in empty_chats:
            db.session.delete(chat)
        db.session.commit()
        print(f"Deleted {count} empty conversation(s).")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))
    debug_mode = app.config.get("DEBUG", True)
    app.run(host="0.0.0.0", port=port, debug=debug_mode)