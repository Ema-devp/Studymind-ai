"""Reusable route decorators."""
import functools

from flask import jsonify, abort
from flask_login import current_user


def json_errors(fn):
    """Catch exceptions in JSON API endpoints and return a clean error payload
    instead of an HTML 500 page."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from app.services.ai_providers.base import (
            AIProviderQuotaError, AIProviderModelUnavailableError, AIProviderAuthError, AIProviderError,
        )

        try:
            return fn(*args, **kwargs)
        except AIProviderQuotaError as e:
            retry_msg = f" Please retry in about {int(e.retry_after_seconds)}s." if e.retry_after_seconds else ""
            return jsonify({
                "success": False,
                "error": (
                    str(e) + retry_msg +
                    " This is a limit on your AI provider account (often a free tier's request "
                    "allowance), not a bug in the app. Fix it by enabling billing on that "
                    "provider's console, switching AI_PROVIDER/model in your .env, or waiting "
                    "for the quota to reset."
                ),
                "error_type": "quota_exceeded",
                "retry_after_seconds": e.retry_after_seconds,
            }), 429
        except AIProviderModelUnavailableError as e:
            return jsonify({
                "success": False,
                "error": (
                    f"The model '{e.model_name}' is not available for your API key "
                    "(commonly because it was deprecated/retired, or restricted to accounts "
                    "that used it before a cutoff date). Check the current model list for "
                    "your provider and update the *_CHAT_MODEL / *_EMBEDDING_MODEL setting "
                    "in your .env, or switch AI_PROVIDER to a different one entirely."
                ),
                "error_type": "model_unavailable",
                "model_name": e.model_name,
            }), 502
        except AIProviderAuthError as e:
            return jsonify({
                "success": False,
                "error": f"AI provider rejected the API key: {e}. Double-check the key in your .env.",
                "error_type": "auth_error",
            }), 502
        except AIProviderError as e:
            return jsonify({"success": False, "error": str(e), "error_type": "ai_service_error"}), 502
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except PermissionError as e:
            return jsonify({"success": False, "error": str(e)}), 403
        except Exception:  # noqa: BLE001
            from flask import current_app

            current_app.logger.exception("Unhandled error in %s", fn.__name__)
            return jsonify({"success": False, "error": "Internal server error"}), 500

    return wrapper


def owns_pdf(fn):
    """Ensure the current user owns the pdf referenced by `pdf_id` kwarg/arg."""

    @functools.wraps(fn)
    def wrapper(*args, pdf_id=None, **kwargs):
        from app.models.pdf import PDF

        pdf = PDF.query.get_or_404(pdf_id)
        if pdf.user_id != current_user.id:
            abort(403)
        return fn(*args, pdf_id=pdf_id, pdf=pdf, **kwargs)

    return wrapper
