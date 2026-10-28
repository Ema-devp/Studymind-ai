"""Small JSON API endpoints backing interactive widgets (Pomodoro timer, bookmarks, analytics)."""
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app import db
from app.models.bookmark import Bookmark
from app.models.study_session import StudySession
from app.models.pdf import PDF
from app.utils.decorators import json_errors

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------- Bookmarks
@api_bp.route("/bookmarks", methods=["GET", "POST"])
@login_required
@json_errors
def bookmarks():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        pdf = PDF.query.get_or_404(data.get("pdf_id"))
        if pdf.user_id != current_user.id:
            return jsonify({"success": False, "error": "Not allowed"}), 403
        bm = Bookmark(
            user_id=current_user.id, pdf_id=pdf.id,
            note=data.get("note"), page_number=data.get("page_number"), excerpt=data.get("excerpt"),
        )
        db.session.add(bm)
        db.session.commit()
        return jsonify({"success": True, "id": bm.id})

    items = current_user.bookmarks.order_by(Bookmark.created_at.desc()).all()
    return jsonify({"success": True, "bookmarks": [
        {"id": b.id, "pdf_id": b.pdf_id, "note": b.note, "page": b.page_number, "excerpt": b.excerpt}
        for b in items
    ]})


@api_bp.route("/bookmarks/<int:bookmark_id>", methods=["DELETE"])
@login_required
@json_errors
def delete_bookmark(bookmark_id):
    bm = Bookmark.query.get_or_404(bookmark_id)
    if bm.user_id != current_user.id:
        return jsonify({"success": False, "error": "Not allowed"}), 403
    db.session.delete(bm)
    db.session.commit()
    return jsonify({"success": True})


# ------------------------------------------------------------ Study Sessions
@api_bp.route("/study-sessions", methods=["POST"])
@login_required
@json_errors
def start_study_session():
    data = request.get_json(silent=True) or {}
    session = StudySession(
        user_id=current_user.id,
        pdf_id=data.get("pdf_id"),
        session_type=data.get("session_type", "pomodoro"),
        duration_minutes=data.get("duration_minutes", 25),
    )
    db.session.add(session)
    db.session.commit()
    return jsonify({"success": True, "id": session.id})


@api_bp.route("/study-sessions/<int:session_id>/complete", methods=["POST"])
@login_required
@json_errors
def complete_study_session(session_id):
    session = StudySession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        return jsonify({"success": False, "error": "Not allowed"}), 403
    session.completed = True
    session.ended_at = datetime.utcnow()
    current_user.register_activity()
    db.session.commit()
    return jsonify({"success": True})


# ------------------------------------------------------------------ Analytics
@api_bp.route("/analytics/progress")
@login_required
@json_errors
def progress_analytics():
    days = int(request.args.get("days", 14))
    since = datetime.utcnow() - timedelta(days=days)
    sessions = current_user.study_sessions.filter(StudySession.started_at >= since).all()

    daily = {}
    for s in sessions:
        day = s.started_at.date().isoformat()
        daily[day] = daily.get(day, 0) + (s.duration_minutes if s.completed else 0)

    return jsonify({"success": True, "daily_minutes": daily, "streak": current_user.study_streak})
