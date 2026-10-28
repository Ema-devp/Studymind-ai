"""
Abstract interface every AI provider (Gemini, OpenAI, Anthropic, ...) must
implement. Every service in this app (RAG, summaries, flashcards, the
assistant widget, etc.) talks only to this interface, never to a specific
vendor SDK - that's what makes switching providers a one-line config change
instead of a code change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class AIProviderError(RuntimeError):
    """Base class for all provider errors. Routes catch this (and its
    subclasses below) to show a friendly message instead of a raw 500."""


class AIProviderQuotaError(AIProviderError):
    """Rate limit / quota exceeded (HTTP 429 equivalent)."""

    def __init__(self, message: str, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AIProviderModelUnavailableError(AIProviderError):
    """Model deprecated, retired, or restricted for this account (HTTP 404
    equivalent, or an invalid/unrecognized model name)."""

    def __init__(self, message: str, model_name: str):
        super().__init__(message)
        self.model_name = model_name


class AIProviderAuthError(AIProviderError):
    """Missing or invalid API key."""


class BaseAIProvider(ABC):
    """Every provider must implement generate/stream for chat, and
    embed_texts/embed_query for embeddings. Providers that don't support
    embeddings (e.g. Anthropic) should set supports_embeddings = False and
    raise AIProviderError with a clear message if those methods are called -
    the app will route embedding calls to a different configured provider
    instead in that case (see ai_providers/__init__.py)."""

    name: str = "base"
    supports_embeddings: bool = True

    def __init__(self, api_key: str, chat_model: str, embedding_model: str | None = None):
        self.api_key = api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model

    @abstractmethod
    def generate(self, prompt: str, system_instruction: str | None = None,
                 temperature: float = 0.4, max_output_tokens: int = 2048) -> str:
        """Single-shot text generation. Returns plain text."""

    @abstractmethod
    def stream(self, prompt: str, system_instruction: str | None = None,
               temperature: float = 0.4) -> Iterable[str]:
        """Yields text chunks as they arrive."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise AIProviderError(
            f"{self.name} does not support embeddings. Set EMBEDDING_PROVIDER in your "
            ".env to a provider that does (e.g. gemini or openai)."
        )

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
