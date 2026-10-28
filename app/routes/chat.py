"""Chat / conversation routes, including the core RAG question-answering endpoint.

New-conversation flow (see fix note): starting a "new chat" does NOT create
a Chat row in the database anymore. It just opens a draft chat view scoped
to a PDF. A Chat row is only created the moment the user actually sends
their first message - so navigating to "New Conversation" and then away
without typing anything no longer leaves behind an empty conversation.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, Response, abort
from flask_login import login_required, current_user

from app import db
from app.models.chat import Chat
from app.models.message import Message
from app.models.pdf import PDF, ProcessingStatus
from app.services import rag_service
from app.services.ai_providers import get_ai_provider, get_embedding_provider
from app.services.vectorstore_service import VectorStoreService
from app.utils.decorators import json_errors

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


def _vectorstore() -> VectorStoreService:
    return VectorStoreService(current_app.config["INDEX_FOLDER"], current_app.config["EMBEDDING_DIMENSIONS"])


def _get_owned_chat(chat_id: int) -> Chat:
    chat = Chat.query.get_or_404(chat_id)
    if chat.user_id != current_user.id:
        abort(403)
    return chat


def _get_owned_pdf(pdf_id: int) -> PDF:
    pdf = PDF.query.get_or_404(pdf_id)
    if pdf.user_id != current_user.id:
        abort(403)
    return pdf


def _answer_and_store(chat: Chat, question: str) -> dict:
    """Runs the RAG pipeline for `question` inside `chat`, persists both the
    user and assistant messages, and returns the JSON-ready assistant
    message payload. Shared by the draft-chat and existing-chat send paths."""
    settings = current_user.settings
    top_k = settings.top_k if settings else current_app.config["DEFAULT_TOP_K"]
    temperature = settings.ai_temperature if settings else current_app.config["DEFAULT_AI_TEMPERATURE"]

    chat_provider = get_ai_provider()
    embedding_provider = get_embedding_provider()

    # Must check this BEFORE adding the new user message below - querying
    # chat.messages.count() after adding it would autoflush the pending
    # insert first and always see it, so "is this the first message" would
    # never be true and the conversation would stay titled "New Conversation".
    is_first_message = chat.title == "New Conversation" and chat.messages.count() == 0

    user_msg = Message(chat_id=chat.id, role="user", content=question)
    db.session.add(user_msg)

    result = rag_service.answer_question(
        pdf_id=chat.pdf_id, question=question, chat_provider=chat_provider,
        embedding_provider=embedding_provider, vectorstore=_vectorstore(),
        top_k=top_k, temperature=temperature,
    )

    assistant_msg = Message(
        chat_id=chat.id, role="assistant",
        content=result.pdf_answer,
        pdf_answer=result.pdf_answer,
        ai_explanation=result.ai_explanation,
        confidence_score=result.confidence,
    )
    assistant_msg.sources = [s.to_dict() for s in result.sources]
    db.session.add(assistant_msg)

    if is_first_message:
        chat.title = rag_service.generate_chat_title(question, chat_provider)

    current_user.register_activity()
    db.session.commit()

    return {
        "id": assistant_msg.id,
        "pdf_answer": assistant_msg.pdf_answer,
        "ai_explanation": assistant_msg.ai_explanation,
        "sources": assistant_msg.sources,
        "confidence": assistant_msg.confidence_score,
    }


@chat_bp.route("/pdf/<int:pdf_id>/new")
@login_required
def new_chat(pdf_id):
    """Opens a draft conversation - nothing is written to the database until
    the first message is actually sent (see /chat/pdf/<pdf_id>/message)."""
    pdf = _get_owned_pdf(pdf_id)
    if pdf.processing_status != ProcessingStatus.COMPLETED:
        flash("This PDF is still processing. Please wait before starting a chat.", "warning")
        return redirect(url_for("pdf.detail", pdf_id=pdf_id))

    other_chats = current_user.chats.filter_by(pdf_id=pdf_id).order_by(Chat.updated_at.desc()).all()
    return render_template("chat/view.html", chat=None, pdf=pdf, other_chats=other_chats)


@chat_bp.route("/pdf/<int:pdf_id>/message", methods=["POST"])
@login_required
@json_errors
def send_draft_message(pdf_id):
    """First message of a brand-new conversation: creates the Chat row now
    (lazily) and then behaves like sending any other message."""
    pdf = _get_owned_pdf(pdf_id)
    if pdf.processing_status != ProcessingStatus.COMPLETED:
        return jsonify({"success": False, "error": "This PDF is still processing."}), 400

    data = request.get_json(silent=True) or request.form
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "error": "Question cannot be empty."}), 400

    chat = Chat(user_id=current_user.id, pdf_id=pdf_id, title="New Conversation")
    db.session.add(chat)
    db.session.flush()  # get chat.id without a separate commit

    message_payload = _answer_and_store(chat, question)

    return jsonify({
        "success": True,
        "chat_id": chat.id,
        "chat_url": url_for("chat.view", chat_id=chat.id),
        "message": message_payload,
        "chat_title": chat.title,
    })


@chat_bp.route("/<int:chat_id>")
@login_required
def view(chat_id):
    chat = _get_owned_chat(chat_id)
    other_chats = current_user.chats.filter_by(pdf_id=chat.pdf_id).order_by(Chat.updated_at.desc()).all()
    return render_template("chat/view.html", chat=chat, pdf=chat.pdf, other_chats=other_chats)


@chat_bp.route("/<int:chat_id>/message", methods=["POST"])
@login_required
@json_errors
def send_message(chat_id):
    chat = _get_owned_chat(chat_id)
    data = request.get_json(silent=True) or request.form
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "error": "Question cannot be empty."}), 400

    message_payload = _answer_and_store(chat, question)

    return jsonify({"success": True, "message": message_payload, "chat_title": chat.title})


@chat_bp.route("/message/<int:message_id>/regenerate", methods=["POST"])
@login_required
@json_errors
def regenerate_message(message_id):
    assistant_msg = Message.query.get_or_404(message_id)
    chat = _get_owned_chat(assistant_msg.chat_id)

    prior_user_msg = (
        Message.query.filter(Message.chat_id == chat.id, Message.role == "user",
                              Message.created_at <= assistant_msg.created_at)
        .order_by(Message.created_at.desc()).first()
    )
    if not prior_user_msg:
        return jsonify({"success": False, "error": "Original question not found."}), 400

    settings = current_user.settings
    top_k = settings.top_k if settings else current_app.config["DEFAULT_TOP_K"]
    temperature = settings.ai_temperature if settings else current_app.config["DEFAULT_AI_TEMPERATURE"]

    result = rag_service.answer_question(
        pdf_id=chat.pdf_id, question=prior_user_msg.content, chat_provider=get_ai_provider(),
        embedding_provider=get_embedding_provider(), vectorstore=_vectorstore(),
        top_k=top_k, temperature=temperature,
    )
    assistant_msg.pdf_answer = result.pdf_answer
    assistant_msg.content = result.pdf_answer
    assistant_msg.ai_explanation = result.ai_explanation
    assistant_msg.confidence_score = result.confidence
    assistant_msg.sources = [s.to_dict() for s in result.sources]
    assistant_msg.is_edited = True
    db.session.commit()

    return jsonify({"success": True, "message": {
        "id": assistant_msg.id, "pdf_answer": assistant_msg.pdf_answer,
        "ai_explanation": assistant_msg.ai_explanation, "sources": assistant_msg.sources,
        "confidence": assistant_msg.confidence_score,
    }})


@chat_bp.route("/message/<int:message_id>", methods=["PUT", "DELETE"])
@login_required
@json_errors
def message_actions(message_id):
    msg = Message.query.get_or_404(message_id)
    _get_owned_chat(msg.chat_id)

    if request.method == "DELETE":
        db.session.delete(msg)
        db.session.commit()
        return jsonify({"success": True})

    data = request.get_json(silent=True) or {}
    new_content = (data.get("content") or "").strip()
    if not new_content:
        return jsonify({"success": False, "error": "Content cannot be empty."}), 400
    msg.content = new_content
    msg.is_edited = True
    db.session.commit()
    return jsonify({"success": True})


@chat_bp.route("/<int:chat_id>/rename", methods=["POST"])
@login_required
@json_errors
def rename_chat(chat_id):
    chat = _get_owned_chat(chat_id)
    data = request.get_json(silent=True) or request.form
    new_title = (data.get("title") or "").strip()
    if not new_title:
        return jsonify({"success": False, "error": "Title cannot be empty."}), 400
    if len(new_title) > 255:
        new_title = new_title[:255]
    chat.title = new_title
    db.session.commit()
    return jsonify({"success": True, "title": chat.title})


@chat_bp.route("/<int:chat_id>/pin", methods=["POST"])
@login_required
@json_errors
def toggle_pin(chat_id):
    chat = _get_owned_chat(chat_id)
    chat.is_pinned = not chat.is_pinned
    db.session.commit()
    return jsonify({"success": True, "is_pinned": chat.is_pinned})


@chat_bp.route("/<int:chat_id>/favorite", methods=["POST"])
@login_required
@json_errors
def toggle_favorite(chat_id):
    chat = _get_owned_chat(chat_id)
    chat.is_favorite = not chat.is_favorite
    db.session.commit()
    return jsonify({"success": True, "is_favorite": chat.is_favorite})


@chat_bp.route("/<int:chat_id>/delete", methods=["POST"])
@login_required
def delete_chat(chat_id):
    chat = _get_owned_chat(chat_id)
    pdf_id = chat.pdf_id
    db.session.delete(chat)
    db.session.commit()
    flash("Conversation deleted.", "info")
    return redirect(url_for("pdf.detail", pdf_id=pdf_id))


@chat_bp.route("/<int:chat_id>/export")
@login_required
def export_chat(chat_id):
    chat = _get_owned_chat(chat_id)
    lines = [f"# {chat.title}", ""]
    for m in chat.messages:
        if m.role == "user":
            lines.append(f"### 🧑 You\n{m.content}\n")
        else:
            lines.append(f"### 🤖 StudyMind AI\n**Answer From PDF:**\n{m.pdf_answer}\n")
            if m.ai_explanation:
                lines.append(f"**AI Explanation:**\n{m.ai_explanation}\n")
    content = "\n".join(lines)
    return Response(
        content, mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=chat_{chat.id}.md"},
    )
