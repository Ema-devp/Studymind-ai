"""OpenAI implementation of BaseAIProvider (Chat Completions + Embeddings)."""
from __future__ import annotations

import logging
from typing import Iterable

from app.services.ai_providers.base import (
    BaseAIProvider, AIProviderError, AIProviderQuotaError,
    AIProviderModelUnavailableError, AIProviderAuthError,
)

logger = logging.getLogger(__name__)

try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None


class OpenAIProvider(BaseAIProvider):
    name = "openai"
    supports_embeddings = True

    def __init__(self, api_key: str, chat_model: str, embedding_model: str | None = None):
        super().__init__(api_key, chat_model, embedding_model)
        if not api_key:
            logger.warning("OPENAI_API_KEY is not set - OpenAI calls will fail until configured.")
        self._client = None

    @property
    def client(self):
        if OpenAI is None:
            raise AIProviderError("openai package is not installed. Run: pip install openai")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def _handle_error(self, e: Exception, context: str, model_name: str) -> None:
        if openai is not None and isinstance(e, openai.RateLimitError):
            raise AIProviderQuotaError(f"The OpenAI API quota/rate limit was exceeded: {e}") from e
        if openai is not None and isinstance(e, openai.NotFoundError):
            raise AIProviderModelUnavailableError(
                f"The model '{model_name}' is not available for this API key.", model_name=model_name,
            ) from e
        if openai is not None and isinstance(e, openai.AuthenticationError):
            raise AIProviderAuthError(f"OpenAI API key was rejected: {e}") from e
        logger.exception("OpenAI %s failed", context)
        raise AIProviderError(f"OpenAI {context} failed: {e}") from e

    def generate(self, prompt: str, system_instruction: str | None = None,
                 temperature: float = 0.4, max_output_tokens: int = 2048) -> str:
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            response = self.client.chat.completions.create(
                model=self.chat_model, messages=messages,
                temperature=temperature, max_tokens=max_output_tokens,
            )
            return (response.choices[0].message.content or "").strip()
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "generate()", self.chat_model)

    def stream(self, prompt: str, system_instruction: str | None = None,
               temperature: float = 0.4) -> Iterable[str]:
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            stream = self.client.chat.completions.create(
                model=self.chat_model, messages=messages, temperature=temperature, stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "stream()", self.chat_model)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(model=self.embedding_model, input=texts)
            return [item.embedding for item in response.data]
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "embed_texts()", self.embedding_model)
