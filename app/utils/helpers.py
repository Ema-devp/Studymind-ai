"""Small, dependency-free helpers used across routes/templates."""
from datetime import datetime


def format_filesize(num_bytes: int) -> str:
    if not num_bytes:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def format_datetime(value: datetime, fmt: str = "%b %d, %Y %H:%M") -> str:
    if not value:
        return ""
    return value.strftime(fmt)


def time_ago(value: datetime) -> str:
    if not value:
        return ""
    diff = datetime.utcnow() - value
    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return format_datetime(value, "%b %d, %Y")


def truncate(text: str, length: int = 120) -> str:
    if not text:
        return ""
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def slugify_filename(filename: str) -> str:
    import re
    import unicodedata

    name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w.\- ]", "", name).strip().replace(" ", "_")
    return name or "file"
