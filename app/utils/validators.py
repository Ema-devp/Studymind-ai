"""Reusable input validation helpers."""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_RE.match(email.strip()))


def password_strength_errors(password: str) -> list[str]:
    """Return a list of human-readable problems with the password (empty = valid)."""
    errors = []
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password or ""):
        errors.append("Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password or ""):
        errors.append("Password must include at least one lowercase letter.")
    if not re.search(r"\d", password or ""):
        errors.append("Password must include at least one number.")
    return errors


def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )
