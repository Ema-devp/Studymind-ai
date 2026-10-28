"""User settings: theme/language, AI/RAG tuning, security, data export & account deletion."""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user, logout_user

from app import db
from app.services.vectorstore_service import VectorStoreService
from app.services import pdf_service
from flask import current_app

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    user_settings = current_user.settings

    if request.method == "POST":
        user_settings.theme = request.form.get("theme", user_settings.theme)
        user_settings.language = request.form.get("language", user_settings.language)
        user_settings.ai_temperature = request.form.get("ai_temperature", user_settings.ai_temperature, type=float)
        user_settings.chunk_size = request.form.get("chunk_size", user_settings.chunk_size, type=int)
        user_settings.chunk_overlap = request.form.get("chunk_overlap", user_settings.chunk_overlap, type=int)
        user_settings.top_k = request.form.get("top_k", user_settings.top_k, type=int)
        user_settings.daily_goal_minutes = request.form.get("daily_goal_minutes", user_settings.daily_goal_minutes, type=int)
        user_settings.email_notifications = bool(request.form.get("email_notifications"))
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings.index"))

    return render_template("settings/index.html", settings=user_settings)


@settings_bp.route("/theme", methods=["POST"])
@login_required
def set_theme():
    """Lightweight endpoint the JS theme-toggle button calls directly."""
    theme = (request.get_json(silent=True) or {}).get("theme")
    if theme in ("dark", "light") and current_user.settings:
        current_user.settings.theme = theme
        db.session.commit()
    return jsonify({"success": True})


@settings_bp.route("/security", methods=["GET", "POST"])
@login_required
def security():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif new_password != confirm:
            flash("New passwords do not match.", "error")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "error")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password changed successfully.", "success")
        return redirect(url_for("settings.security"))

    return render_template("settings/security.html")


@settings_bp.route("/export-data")
@login_required
def export_data():
    payload = {
        "user": {"name": current_user.name, "email": current_user.email, "created_at": str(current_user.created_at)},
        "pdfs": [{"title": p.title, "pages": p.page_count, "uploaded": str(p.created_at)} for p in current_user.pdfs],
        "chats": [{"title": c.title, "messages": c.messages.count()} for c in current_user.chats],
        "settings": current_user.settings.to_dict() if current_user.settings else {},
    }
    return Response(
        json.dumps(payload, indent=2), mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=studymind_export.json"},
    )


@settings_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    confirm_email = request.form.get("confirm_email", "").strip().lower()
    if confirm_email != current_user.email.lower():
        flash("Email confirmation did not match. Account was not deleted.", "error")
        return redirect(url_for("settings.index"))

    vectorstore = VectorStoreService(current_app.config["INDEX_FOLDER"], current_app.config["EMBEDDING_DIMENSIONS"])
    for pdf in current_user.pdfs.all():
        try:
            pdf_service.delete_pdf(pdf, vectorstore)
        except Exception:  # noqa: BLE001
            pass

    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("Your account has been deleted.", "info")
    return redirect(url_for("auth.login"))
