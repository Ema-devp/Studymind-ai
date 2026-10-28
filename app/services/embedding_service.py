"""Generates embeddings for text chunks in batches (to stay under API limits)."""
from __future__ import annotations

import logging

from app.services.ai_providers.base import BaseAIProvider

logger = logging.getLogger(__name__)

BATCH_SIZE = 32


def embed_chunks(embedding_provider: BaseAIProvider, texts: list[str]) -> list[list[float]]:
    """Embeds a list of chunk texts, batching requests."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        logger.info("Embedding batch %d-%d of %d chunks", i, i + len(batch), len(texts))
        vectors.extend(embedding_provider.embed_texts(batch))
    return vectors


def embed_query(embedding_provider: BaseAIProvider, query: str) -> list[float]:
    return embedding_provider.embed_query(query)
