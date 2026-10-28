"""Global search across PDFs, chats, messages, and flashcards."""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.models.pdf import PDF
from app.models.chat import Chat
from app.models.message import Message
from app.models.flashcard import FlashcardSet

search_bp = Blueprint("search", __name__, url_prefix="/search")


@search_bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    results = {"pdfs": [], "chats": [], "messages": [], "flashcard_sets": []}

    if q:
        like = f"%{q}%"
        results["pdfs"] = current_user.pdfs.filter(PDF.title.ilike(like)).limit(15).all()
        results["chats"] = current_user.chats.filter(Chat.title.ilike(like)).limit(15).all()
        results["messages"] = (
            Message.query.join(Chat).filter(Chat.user_id == current_user.id, Message.content.ilike(like))
            .limit(15).all()
        )
        results["flashcard_sets"] = current_user.flashcard_sets.filter(FlashcardSet.title.ilike(like)).limit(15).all()

    return render_template("dashboard/search_results.html", query=q, results=results)
