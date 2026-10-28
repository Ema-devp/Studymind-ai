"""
Sends verification and password-reset emails.

If MAIL_SERVER is left blank (the default), we don't attempt to send real
email - we log the link instead, which keeps local development working with
zero setup. Configure MAIL_SERVER/MAIL_USERNAME/MAIL_PASSWORD in .env to
send real email through any SMTP provider (Gmail, SendGrid, Mailgun, SES...).
"""
from __future__ import annotations

import logging

from flask import current_app, render_template
from flask_mail import Message as MailMessage

from app import mail

logger = logging.getLogger(__name__)


class EmailSendError(RuntimeError):
    pass


def _mail_is_configured() -> bool:
    return bool(current_app.config.get("MAIL_SERVER"))


def _send(subject: str, recipient: str, html_body: str, text_body: str) -> None:
    if not _mail_is_configured():
        logger.info(
            "MAIL_SERVER not configured - not sending real email. "
            "Subject: %r  To: %s\n%s", subject, recipient, text_body,
        )
        return

    try:
        msg = MailMessage(
            subject=subject,
            recipients=[recipient],
            body=text_body,
            html=html_body,
            sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
        )
        mail.send(msg)
    except Exception as e:  # noqa: BLE001
        # Email failures should never break registration/reset flows for the
        # user - log it and let the caller decide whether to also flash a
        # warning (the console-logged link is always the fallback).
        logger.exception("Failed to send email to %s: %s", recipient, e)
        raise EmailSendError(str(e)) from e


def send_verification_email(user, verify_url: str) -> None:
    subject = "Verify your StudyMind AI account"
    text_body = (
        f"Hi {user.name},\n\n"
        f"Welcome to StudyMind AI! Please verify your email by visiting:\n{verify_url}\n\n"
        "If you didn't create this account, you can ignore this email."
    )
    html_body = render_template(
        "email/verify_email.html", user=user, verify_url=verify_url,
    )
    _send(subject, user.email, html_body, text_body)


def send_password_reset_email(user, reset_url: str) -> None:
    subject = "Reset your StudyMind AI password"
    text_body = (
        f"Hi {user.name},\n\n"
        f"We received a request to reset your password. Visit this link to choose a new one "
        f"(expires in 30 minutes):\n{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    html_body = render_template(
        "email/reset_password.html", user=user, reset_url=reset_url,
    )
    _send(subject, user.email, html_body, text_body)
