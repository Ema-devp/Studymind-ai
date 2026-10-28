"""
Sitewide 'Ask StudyMind' assistant widget - a general-purpose helper (not
grounded in any particular PDF) available from a floating chat bubble on
every authenticated page, similar to how Claude's own chat works: ask it
anything about using the app, studying strategies, or general questions.

This intentionally does NOT use Dual Answer Mode or RAG - it's a plain
conversational assistant, backed by whichever AI provider is configured.
"""
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from app import db
from app.models.assistant_message import AssistantMessage
from app.services.ai_providers import get_ai_provider
from app.utils.decorators import json_errors

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

SYSTEM_PROMPT = """You are the "Ask StudyMind" assistant embedded in StudyMind AI, an app where students \
upload PDFs and get AI-powered summaries, flashcards, quizzes, and chat answers grounded in their documents.

You are a general-purpose helper distinct from the per-document chat: you don't have access to any specific \
PDF the user has uploaded. If the user asks a question that's clearly about the content of one of their \
documents, gently point them to open that PDF and use its dedicated chat instead, which can actually read it.

Otherwise, help with anything: how to use the app's features, general study tips and strategies, explaining \
concepts, or just being a friendly conversational assistant. Keep answers concise and use Markdown when helpful."""

MAX_CONTEXT_MESSAGES = 12  # how much recent history to feed back as context


def _recent_history_as_prompt(user_id: int) -> str:
    recent = (
        AssistantMessage.query.filter_by(user_id=user_id)
        .order_by(AssistantMessage.created_at.desc())
        .limit(MAX_CONTEXT_MESSAGES)
        .all()
    )
    recent.reverse()
    lines = []
    for m in recent:
        speaker = "User" if m.role == "user" else "Assistant"
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines)


@assistant_bp.route("/history")
@login_required
@json_errors
def history():
    limit = current_app.config.get("ASSISTANT_HISTORY_LIMIT", 50)
    messages = (
        AssistantMessage.query.filter_by(user_id=current_user.id)
        .order_by(AssistantMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    return jsonify({
        "success": True,
        "messages": [{"id": m.id, "role": m.role, "content": m.content} for m in messages],
    })


@assistant_bp.route("/message", methods=["POST"])
@login_required
@json_errors
def send_message():
    data = request.get_json(silent=True) or {}
    question = (data.get("message") or "").strip()
    if not question:
        return jsonify({"success": False, "error": "Message cannot be empty."}), 400
    if len(question) > 4000:
        return jsonify({"success": False, "error": "Message is too long (max 4000 characters)."}), 400

    user_msg = AssistantMessage(user_id=current_user.id, role="user", content=question)
    db.session.add(user_msg)
    db.session.flush()

    history_prompt = _recent_history_as_prompt(current_user.id)
    prompt = f"{history_prompt}\n\nUser: {question}" if history_prompt else question

    provider = get_ai_provider()
    reply = provider.generate(prompt, system_instruction=SYSTEM_PROMPT, temperature=0.6, max_output_tokens=1024)

    assistant_msg = AssistantMessage(user_id=current_user.id, role="assistant", content=reply)
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": {"id": assistant_msg.id, "role": "assistant", "content": reply},
    })


@assistant_bp.route("/clear", methods=["POST"])
@login_required
@json_errors
def clear_history():
    AssistantMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"success": True})
