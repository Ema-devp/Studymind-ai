"""Authentication & profile routes."""
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app import db, limiter
from app.models.user import User
from app.models.settings import UserSettings
from app.services import email_service
from app.services.email_service import EmailSendError
from app.utils.validators import is_valid_email, password_strength_errors

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not name:
            errors.append("Please enter your name.")
        if not is_valid_email(email):
            errors.append("Please enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")
        errors += password_strength_errors(password)
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html", name=name, email=email)

        user = User(name=name, email=email)
        user.set_password(password)
        token = user.generate_email_verify_token()
        db.session.add(user)
        db.session.flush()  # get user.id before creating settings

        db.session.add(UserSettings(user_id=user.id))
        db.session.commit()

        # In production this token would be emailed - and now it actually is,
        # if MAIL_SERVER is configured. Otherwise it's logged to the console.
        verify_url = url_for("auth.verify_email", token=token, _external=True)
        try:
            email_service.send_verification_email(user, verify_url)
        except EmailSendError:
            pass  # already logged; don't block registration on email failure
        if current_app.config.get("MAIL_SERVER"):
            flash("Account created! Check your email for a verification link, then log in below.", "success")
        else:
            flash("Account created! Email sending isn't configured, so check the server console for your verification link, then log in below.", "success")

        # Do NOT log the user in yet - email verification is required first.
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_email_verified:
                flash(
                    "Please verify your email before logging in. Check your inbox for the "
                    "verification link, or request a new one below.",
                    "error",
                )
                return render_template("auth/login.html", email=email, show_resend=True)

            login_user(user, remember=remember)
            user.register_activity()
            db.session.commit()
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.index"))

        flash("Invalid email or password.", "error")
        return render_template("auth/login.html", email=email)

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    user = User.query.filter_by(email_verify_token=token).first()
    if not user:
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for("auth.login"))
    user.is_email_verified = True
    user.email_verify_token = None
    db.session.commit()
    flash("Email verified successfully!", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["POST"])
@login_required
@limiter.limit("5 per hour")
def resend_verification():
    if current_user.is_email_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for("auth.profile"))

    token = current_user.generate_email_verify_token()
    db.session.commit()
    verify_url = url_for("auth.verify_email", token=token, _external=True)
    try:
        email_service.send_verification_email(current_user, verify_url)
    except EmailSendError:
        pass
    if current_app.config.get("MAIL_SERVER"):
        flash("Verification email sent.", "success")
    else:
        flash("Email sending isn't configured - check the server console for your verification link.", "info")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/resend-verification-email", methods=["POST"])
@limiter.limit("5 per hour")
def resend_verification_public():
    """Same as resend_verification, but reachable without a session - since
    an unverified account can never log in, they'd otherwise have no way to
    request a fresh link if the first email was lost or expired."""
    email = request.form.get("email", "").strip().lower()
    user = User.query.filter_by(email=email).first()

    if user and not user.is_email_verified:
        token = user.generate_email_verify_token()
        db.session.commit()
        verify_url = url_for("auth.verify_email", token=token, _external=True)
        try:
            email_service.send_verification_email(user, verify_url)
        except EmailSendError:
            pass

    # Same message regardless of outcome - don't leak which emails exist or
    # are already verified.
    if current_app.config.get("MAIL_SERVER"):
        flash("If that email exists and isn't verified yet, a new verification link has been sent.", "info")
    else:
        flash(
            "If that email exists and isn't verified yet, a new verification link has been "
            "logged to the server console (email sending isn't configured).",
            "info",
        )
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            try:
                email_service.send_password_reset_email(user, reset_url)
            except EmailSendError:
                pass  # already logged; the console fallback still has the link
        # Always show the same message so we don't leak which emails are registered
        if current_app.config.get("MAIL_SERVER"):
            flash("If an account exists for that email, a reset link has been sent.", "info")
        else:
            flash("If an account exists for that email, a reset link has been logged to the server console (email sending isn't configured).", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_password_token=token).first()
    if not user or not user.reset_token_valid(token):
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = password_strength_errors(password)
        if password != confirm:
            errors.append("Passwords do not match.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/reset_password.html", token=token)

        user.set_password(password)
        user.clear_reset_token()
        db.session.commit()
        flash("Password updated. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name).strip()
        avatar_url = request.form.get("avatar_url", "").strip()
        if avatar_url:
            current_user.avatar_url = avatar_url
        current_user.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")
