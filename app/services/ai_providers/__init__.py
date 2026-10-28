"""
Provider factory.

The whole point of this module: switching AI vendors should require adding
one API key to `.env` and nothing else. If `AI_PROVIDER` is left as "auto"
(the default), we pick the first provider - in priority order gemini,
openai, anthropic - whose API key is actually set. Setting AI_PROVIDER
explicitly overrides auto-detection when more than one key is present.

Embeddings work the same way via EMBEDDING_PROVIDER, except Anthropic is
skipped for embeddings (it has no embeddings API) - if AI_PROVIDER is
anthropic and no embedding-capable key is configured, we raise a clear
error rather than silently failing deep inside the RAG pipeline.
"""
from __future__ import annotations

from flask import current_app

from app.services.ai_providers.base import AIProviderError, BaseAIProvider
from app.services.ai_providers.gemini_provider import GeminiProvider
from app.services.ai_providers.openai_provider import OpenAIProvider
from app.services.ai_providers.anthropic_provider import AnthropicProvider

# Re-exported so callers can `from app.services.ai_providers import AIProviderQuotaError` etc.
from app.services.ai_providers.base import (  # noqa: F401
    AIProviderQuotaError, AIProviderModelUnavailableError, AIProviderAuthError,
)

_PROVIDER_PRIORITY = ["gemini", "openai", "anthropic"]

_PROVIDER_CLASSES = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def _api_key_for(provider_name: str, cfg) -> str:
    return {
        "gemini": cfg.get("GEMINI_API_KEY", ""),
        "openai": cfg.get("OPENAI_API_KEY", ""),
        "anthropic": cfg.get("ANTHROPIC_API_KEY", ""),
    }.get(provider_name, "")


def _detect_provider_name(cfg, require_embeddings: bool = False) -> str:
    candidates = _PROVIDER_PRIORITY
    if require_embeddings:
        candidates = [p for p in candidates if _PROVIDER_CLASSES[p].supports_embeddings]
    for name in candidates:
        if _api_key_for(name, cfg):
            return name
    # Nothing configured - default to gemini so error messages point somewhere concrete
    return candidates[0] if candidates else "gemini"


def _build_provider(provider_name: str, cfg, chat_model_override: str | None = None,
                     embedding_model_override: str | None = None) -> BaseAIProvider:
    provider_name = provider_name.lower()
    if provider_name not in _PROVIDER_CLASSES:
        raise AIProviderError(
            f"Unknown AI_PROVIDER '{provider_name}'. Valid options: {', '.join(_PROVIDER_CLASSES)}."
        )
    cls = _PROVIDER_CLASSES[provider_name]
    api_key = _api_key_for(provider_name, cfg)

    defaults = {
        "gemini": (cfg.get("GEMINI_CHAT_MODEL"), cfg.get("GEMINI_EMBEDDING_MODEL")),
        "openai": (cfg.get("OPENAI_CHAT_MODEL"), cfg.get("OPENAI_EMBEDDING_MODEL")),
        "anthropic": (cfg.get("ANTHROPIC_CHAT_MODEL"), None),
    }
    default_chat_model, default_embedding_model = defaults[provider_name]

    return cls(
        api_key=api_key,
        chat_model=chat_model_override or default_chat_model,
        embedding_model=embedding_model_override or default_embedding_model,
    )


def get_ai_provider() -> BaseAIProvider:
    """Returns the provider to use for chat/generation (summaries, RAG
    answers, the assistant widget, etc.)."""
    cfg = current_app.config
    configured = (cfg.get("AI_PROVIDER") or "auto").lower()
    provider_name = configured if configured != "auto" else _detect_provider_name(cfg)
    return _build_provider(provider_name, cfg)


def get_embedding_provider() -> BaseAIProvider:
    """Returns the provider to use for embeddings. Falls back away from
    Anthropic (which has no embeddings API) even if it's the configured
    chat provider, unless the user explicitly forces it via
    EMBEDDING_PROVIDER (in which case we raise a clear error)."""
    cfg = current_app.config
    configured = (cfg.get("EMBEDDING_PROVIDER") or "auto").lower()

    if configured != "auto":
        provider_name = configured
    else:
        # Prefer whatever the chat provider is, as long as it supports
        # embeddings; otherwise auto-detect an embedding-capable one.
        chat_configured = (cfg.get("AI_PROVIDER") or "auto").lower()
        chat_provider_name = chat_configured if chat_configured != "auto" else _detect_provider_name(cfg)
        if _PROVIDER_CLASSES[chat_provider_name].supports_embeddings and _api_key_for(chat_provider_name, cfg):
            provider_name = chat_provider_name
        else:
            provider_name = _detect_provider_name(cfg, require_embeddings=True)

    cls = _PROVIDER_CLASSES.get(provider_name)
    if cls is None or not cls.supports_embeddings:
        raise AIProviderError(
            f"'{provider_name}' does not support embeddings. Set EMBEDDING_PROVIDER in your "
            ".env to 'gemini' or 'openai' (with the matching API key set), since PDF "
            "processing and chat require an embeddings-capable provider."
        )
    if not _api_key_for(provider_name, cfg):
        raise AIProviderError(
            f"Embeddings would use '{provider_name}' but no API key is set for it. "
            "Add GEMINI_API_KEY or OPENAI_API_KEY to your .env, or set EMBEDDING_PROVIDER explicitly."
        )
    return _build_provider(provider_name, cfg)
