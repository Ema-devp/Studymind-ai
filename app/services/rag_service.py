"""
Retrieval-Augmented Generation pipeline.

For every user question:
  1. Embed the question
  2. Search the PDF's FAISS index for the top-k most similar chunks
  3. Ask Gemini for a strictly grounded "Answer From PDF" using only those
     chunks, plus a separate "AI Explanation" using general knowledge
  4. Return both answers, the source chunks used, and a confidence score
     derived from retrieval similarity
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.models.chunk import Chunk
from app.services.ai_providers.base import BaseAIProvider
from app.services.vectorstore_service import VectorStoreService

logger = logging.getLogger(__name__)

PDF_ANSWER_SYSTEM_PROMPT = """You are StudyMind AI's document assistant. You answer questions using ONLY \
the provided excerpts from the user's uploaded PDF. Rules:
- Do not use outside knowledge in this answer.
- If the excerpts do not contain the answer, respond EXACTLY with: \
"I could not find this information in the uploaded PDF."
- Be precise and cite specific facts from the excerpts.
- Keep the answer focused and well-structured, using Markdown when helpful."""

AI_EXPLANATION_SYSTEM_PROMPT = """You are StudyMind AI's tutor. Explain the topic the user asked about in \
simple, clear language, as if teaching a student. You may use your general knowledge (not limited to the \
PDF excerpts). Keep it approachable, use short paragraphs or bullet points, and define any technical terms."""

NOT_FOUND_PHRASE = "I could not find this information in the uploaded pdf."


@dataclass
class SourceRef:
    chunk_id: int
    page_number: int | None
    snippet: str
    score: float

    def to_dict(self):
        return {
            "chunk_id": self.chunk_id,
            "page": self.page_number,
            "snippet": self.snippet,
            "score": round(self.score, 4),
        }


@dataclass
class RAGResult:
    pdf_answer: str
    ai_explanation: str
    sources: list[SourceRef] = field(default_factory=list)
    confidence: float = 0.0


def retrieve_chunks(pdf_id: int, question: str, embedding_provider: BaseAIProvider,
                     vectorstore: VectorStoreService, top_k: int = 5) -> list[SourceRef]:
    query_vector = embedding_provider.embed_query(question)
    hits = vectorstore.search(pdf_id, query_vector, top_k=top_k)

    sources: list[SourceRef] = []
    for vector_id, score in hits:
        chunk = Chunk.query.filter_by(pdf_id=pdf_id, vector_id=vector_id).first()
        if not chunk:
            continue
        snippet = chunk.content[:400] + ("…" if len(chunk.content) > 400 else "")
        sources.append(SourceRef(chunk_id=chunk.id, page_number=chunk.page_number, snippet=snippet, score=score))
    return sources


def _build_context(sources: list[SourceRef]) -> str:
    parts = []
    for i, s in enumerate(sources, start=1):
        page = f"page {s.page_number}" if s.page_number else "unknown page"
        parts.append(f"[Excerpt {i} - {page}]\n{s.snippet}")
    return "\n\n".join(parts)


def _confidence_from_scores(sources: list[SourceRef]) -> float:
    if not sources:
        return 0.0
    top = sources[0].score
    # Cosine similarity via normalized inner product is already ~[-1, 1]; clip to [0, 1]
    return max(0.0, min(1.0, top))


def answer_question(
    pdf_id: int,
    question: str,
    chat_provider: BaseAIProvider,
    embedding_provider: BaseAIProvider,
    vectorstore: VectorStoreService,
    top_k: int = 5,
    temperature: float = 0.4,
) -> RAGResult:
    sources = retrieve_chunks(pdf_id, question, embedding_provider, vectorstore, top_k=top_k)

    if not sources:
        pdf_answer = "I could not find this information in the uploaded PDF."
    else:
        context = _build_context(sources)
        prompt = (
            f"Document excerpts:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer the question using only the excerpts above."
        )
        pdf_answer = chat_provider.generate(
            prompt, system_instruction=PDF_ANSWER_SYSTEM_PROMPT, temperature=temperature
        )

    explanation_prompt = f"Question: {question}\n\nExplain this topic simply, as if teaching a beginner."
    ai_explanation = chat_provider.generate(
        explanation_prompt, system_instruction=AI_EXPLANATION_SYSTEM_PROMPT, temperature=temperature
    )

    confidence = 0.0 if pdf_answer.strip().lower().startswith(NOT_FOUND_PHRASE) else _confidence_from_scores(sources)

    return RAGResult(pdf_answer=pdf_answer, ai_explanation=ai_explanation, sources=sources, confidence=confidence)


def generate_chat_title(question: str, chat_provider: BaseAIProvider) -> str:
    """Short (3-6 word) title for a new conversation, based on the first message."""
    try:
        title = chat_provider.generate(
            f"Create a short 3-6 word title (no punctuation, no quotes) for a study chat that starts "
            f"with this question:\n\n{question}",
            temperature=0.3,
            max_output_tokens=20,
        )
        return title.strip().strip('"').strip("'")[:80] or question[:50]
    except Exception:  # noqa: BLE001
        return question[:50]
