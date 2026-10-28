"""Anthropic (Claude) implementation of BaseAIProvider.

Anthropic has no embeddings API, so this provider only supports chat
generation. If EMBEDDING_PROVIDER resolves to 'anthropic' (or AI_PROVIDER
is anthropic and no separate embedding provider is configured), the
provider factory falls back to Gemini or OpenAI automatically - see
ai_providers/__init__.py.
"""
from __future__ import annotations

import logging
from typing import Iterable

from app.services.ai_providers.base import (
    BaseAIProvider, AIProviderError, AIProviderQuotaError,
    AIProviderModelUnavailableError, AIProviderAuthError,
)

logger = logging.getLogger(__name__)

try:
    import anthropic
    from anthropic import Anthropic
except ImportError:
    anthropic = None
    Anthropic = None


class AnthropicProvider(BaseAIProvider):
    name = "anthropic"
    supports_embeddings = False

    def __init__(self, api_key: str, chat_model: str, embedding_model: str | None = None):
        super().__init__(api_key, chat_model, embedding_model)
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY is not set - Claude calls will fail until configured.")
        self._client = None

    @property
    def client(self):
        if Anthropic is None:
            raise AIProviderError("anthropic package is not installed. Run: pip install anthropic")
        if self._client is None:
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def _handle_error(self, e: Exception, context: str, model_name: str) -> None:
        if anthropic is not None and isinstance(e, anthropic.RateLimitError):
            raise AIProviderQuotaError(f"The Anthropic API quota/rate limit was exceeded: {e}") from e
        if anthropic is not None and isinstance(e, anthropic.NotFoundError):
            raise AIProviderModelUnavailableError(
                f"The model '{model_name}' is not available for this API key.", model_name=model_name,
            ) from e
        if anthropic is not None and isinstance(e, anthropic.AuthenticationError):
            raise AIProviderAuthError(f"Anthropic API key was rejected: {e}") from e
        logger.exception("Anthropic %s failed", context)
        raise AIProviderError(f"Anthropic {context} failed: {e}") from e

    def generate(self, prompt: str, system_instruction: str | None = None,
                 temperature: float = 0.4, max_output_tokens: int = 2048) -> str:
        try:
            response = self.client.messages.create(
                model=self.chat_model,
                system=system_instruction or "",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_output_tokens,
            )
            return "".join(block.text for block in response.content if block.type == "text").strip()
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "generate()", self.chat_model)

    def stream(self, prompt: str, system_instruction: str | None = None,
               temperature: float = 0.4) -> Iterable[str]:
        try:
            with self.client.messages.stream(
                model=self.chat_model,
                system=system_instruction or "",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=4096,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "stream()", self.chat_model)
