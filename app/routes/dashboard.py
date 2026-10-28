"""Dashboard: recent activity, stats, study streak, quick actions."""
from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models.pdf import PDF, ProcessingStatus
from app.models.chat import Chat
from app.models.study_session import StudySession

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/")


@dashboard_bp.route("/")
@login_required
def index():
    recent_pdfs = current_user.pdfs.order_by(PDF.created_at.desc()).limit(6).all()
    recent_chats = current_user.chats.order_by(Chat.updated_at.desc()).limit(6).all()

    total_pdfs = current_user.pdfs.count()
    total_chats = current_user.chats.count()
    completed_pdfs = current_user.pdfs.filter_by(processing_status=ProcessingStatus.COMPLETED).count()

    week_ago = datetime.utcnow() - timedelta(days=7)
    minutes_this_week = (
        current_user.study_sessions.filter(StudySession.started_at >= week_ago, StudySession.completed.is_(True))
        .with_entities(StudySession.duration_minutes)
        .all()
    )
    minutes_this_week_total = sum(m[0] for m in minutes_this_week) if minutes_this_week else 0

    stats = {
        "total_pdfs": total_pdfs,
        "completed_pdfs": completed_pdfs,
        "total_chats": total_chats,
        "study_streak": current_user.study_streak,
        "minutes_this_week": minutes_this_week_total,
    }

    return render_template(
        "dashboard/index.html",
        recent_pdfs=recent_pdfs,
        recent_chats=recent_chats,
        stats=stats,
    )
