"""Google Gemini implementation of BaseAIProvider."""
from __future__ import annotations

import logging
import re
from typing import Iterable

from app.services.ai_providers.base import (
    BaseAIProvider, AIProviderError, AIProviderQuotaError,
    AIProviderModelUnavailableError, AIProviderAuthError,
)

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None


def _is_quota_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    return "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc)


def _is_model_not_found_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 404:
        return True
    return "NOT_FOUND" in str(exc) or " 404 " in f" {exc} "


def _is_auth_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code in (401, 403) or "API_KEY_INVALID" in str(exc) or "PERMISSION_DENIED" in str(exc)


def _extract_retry_delay(exc: Exception) -> float | None:
    match = re.search(r"retry in ([\d.]+)s", str(exc))
    return float(match.group(1)) if match else None


class GeminiProvider(BaseAIProvider):
    name = "gemini"
    supports_embeddings = True

    def __init__(self, api_key: str, chat_model: str, embedding_model: str | None = None):
        super().__init__(api_key, chat_model, embedding_model)
        if not api_key:
            logger.warning("GEMINI_API_KEY is not set - Gemini calls will fail until configured.")
        self._client = None

    @property
    def client(self):
        if genai is None:
            raise AIProviderError("google-genai package is not installed. Run: pip install google-genai")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _handle_error(self, e: Exception, context: str, model_name: str) -> None:
        if _is_quota_error(e):
            logger.warning("Gemini quota/rate-limit hit in %s: %s", context, e)
            raise AIProviderQuotaError(
                "The Gemini API quota for this project/model has been exceeded.",
                retry_after_seconds=_extract_retry_delay(e),
            ) from e
        if _is_model_not_found_error(e):
            logger.warning("Gemini model '%s' not found/unavailable: %s", model_name, e)
            raise AIProviderModelUnavailableError(
                f"The model '{model_name}' is not available for this API key "
                "(it may be deprecated, retired, or restricted to existing users only).",
                model_name=model_name,
            ) from e
        if _is_auth_error(e):
            raise AIProviderAuthError(f"Gemini API key was rejected: {e}") from e
        logger.exception("Gemini %s failed", context)
        raise AIProviderError(f"Gemini {context} failed: {e}") from e

    def generate(self, prompt: str, system_instruction: str | None = None,
                 temperature: float = 0.4, max_output_tokens: int = 2048) -> str:
        try:
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            response = self.client.models.generate_content(
                model=self.chat_model, contents=prompt, config=config,
            )
            return (response.text or "").strip()
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "generate()", self.chat_model)

    def stream(self, prompt: str, system_instruction: str | None = None,
               temperature: float = 0.4) -> Iterable[str]:
        try:
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction, temperature=temperature,
            )
            for chunk in self.client.models.generate_content_stream(
                model=self.chat_model, contents=prompt, config=config
            ):
                if chunk.text:
                    yield chunk.text
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "stream()", self.chat_model)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            result = self.client.models.embed_content(model=self.embedding_model, contents=texts)
            return [e.values for e in result.embeddings]
        except AIProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            self._handle_error(e, "embed_texts()", self.embedding_model)
