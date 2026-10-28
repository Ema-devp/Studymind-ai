"""
Generates study material (summaries, flashcards, quizzes, notes, etc.) from
a PDF's full extracted text. All prompts request strict JSON where the
output feeds structured UI (flashcards/quiz), and Markdown where the output
is read directly (summaries/notes).
"""
from __future__ import annotations

import json
import logging
import re

from app.models.chunk import Chunk
from app.services.ai_providers.base import BaseAIProvider

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 24000  # keep prompts within a reasonable token budget


def _document_text(pdf_id: int, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    chunks = Chunk.query.filter_by(pdf_id=pdf_id).order_by(Chunk.chunk_index).all()
    text = "\n\n".join(c.content for c in chunks)
    return text[:max_chars]


def _extract_json(raw: str):
    """Gemini sometimes wraps JSON in markdown fences; strip them defensively."""
    cleaned = re.sub(r"^```json\s*|^```\s*|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


# ----------------------------------------------------------------------
# Summaries
# ----------------------------------------------------------------------
def generate_summary(pdf_id: int, chat_provider: BaseAIProvider, style: str = "detailed") -> str:
    """style: 'short' | 'detailed' | 'bullet'"""
    text = _document_text(pdf_id)
    instructions = {
        "short": "Write a concise 3-5 sentence summary capturing only the most important idea.",
        "detailed": "Write a thorough, well-organized summary with headings covering all major sections.",
        "bullet": "Write a bullet-point summary with a top-level bullet per major topic and nested "
                  "sub-bullets for key details.",
    }.get(style, "Write a thorough summary.")

    prompt = f"Document:\n{text}\n\nTask: {instructions}\nRespond in Markdown."
    return chat_provider.generate(prompt, system_instruction="You are a precise academic summarizer.", temperature=0.3)


# ----------------------------------------------------------------------
# Flashcards
# ----------------------------------------------------------------------
def generate_flashcards(pdf_id: int, chat_provider: BaseAIProvider, count: int = 12) -> list[dict]:
    text = _document_text(pdf_id)
    prompt = (
        f"Document:\n{text}\n\n"
        f"Create exactly {count} flashcards covering the most important concepts. "
        'Respond ONLY with a JSON array like: '
        '[{"front": "question or term", "back": "answer or definition", "difficulty": "easy|medium|hard"}]. '
        "No markdown fences, no commentary."
    )
    raw = chat_provider.generate(prompt, system_instruction="You output only valid JSON.", temperature=0.4)
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        logger.warning("Flashcard JSON parse failed, returning empty list. Raw: %s", raw[:300])
        return []


# ----------------------------------------------------------------------
# Quizzes
# ----------------------------------------------------------------------
def generate_quiz(pdf_id: int, chat_provider: BaseAIProvider, quiz_type: str = "mcq",
                   count: int = 10, difficulty: str = "medium") -> list[dict]:
    text = _document_text(pdf_id)

    type_instructions = {
        "mcq": 'Each item: {"type": "mcq", "question": "...", "options": ["A", "B", "C", "D"], '
               '"correct_answer": "the exact correct option text", "explanation": "..."}',
        "true_false": 'Each item: {"type": "true_false", "question": "...", "options": ["True", "False"], '
                       '"correct_answer": "True or False", "explanation": "..."}',
        "fill_blank": 'Each item: {"type": "fill_blank", "question": "sentence with ____ for the blank", '
                       '"options": [], "correct_answer": "the missing word/phrase", "explanation": "..."}',
    }
    instruction = type_instructions.get(quiz_type, type_instructions["mcq"])

    prompt = (
        f"Document:\n{text}\n\n"
        f"Create exactly {count} {difficulty}-difficulty quiz questions of type '{quiz_type}'. "
        f"Respond ONLY with a JSON array. Format per item: {instruction}. No markdown fences."
    )
    raw = chat_provider.generate(prompt, system_instruction="You output only valid JSON.", temperature=0.4)
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        logger.warning("Quiz JSON parse failed, returning empty list. Raw: %s", raw[:300])
        return []


# ----------------------------------------------------------------------
# Misc study tools
# ----------------------------------------------------------------------
def explain_like_im_10(pdf_id: int, chat_provider: BaseAIProvider, topic: str) -> str:
    text = _document_text(pdf_id)
    prompt = f"Document:\n{text}\n\nExplain '{topic}' like I'm 10 years old, using a simple analogy."
    return chat_provider.generate(prompt, system_instruction="You are a friendly, patient teacher.", temperature=0.6)


def generate_study_notes(pdf_id: int, chat_provider: BaseAIProvider) -> str:
    text = _document_text(pdf_id)
    prompt = (
        f"Document:\n{text}\n\n"
        "Create structured revision notes in Markdown: headings per topic, key definitions in bold, "
        "and a short 'Key Takeaways' bullet list at the end."
    )
    return chat_provider.generate(prompt, system_instruction="You create excellent exam revision notes.", temperature=0.3)


def generate_mind_map_outline(pdf_id: int, chat_provider: BaseAIProvider) -> dict:
    """Returns a nested JSON tree {title, children: [...]} suitable for rendering a mind map."""
    text = _document_text(pdf_id)
    prompt = (
        f"Document:\n{text}\n\n"
        'Create a mind map as JSON: {"title": "Central Topic", "children": '
        '[{"title": "Branch", "children": [{"title": "Leaf", "children": []}]}]}. '
        "Max depth 3, max 6 children per node. JSON only, no markdown fences."
    )
    raw = chat_provider.generate(prompt, system_instruction="You output only valid JSON.", temperature=0.4)
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        return {"title": "Mind Map", "children": []}


def generate_important_questions(pdf_id: int, chat_provider: BaseAIProvider, count: int = 10) -> str:
    text = _document_text(pdf_id)
    prompt = f"Document:\n{text}\n\nList the {count} most important exam-style questions a student should prepare, in Markdown, grouped by topic."
    return chat_provider.generate(prompt, temperature=0.4)


def generate_interview_questions(pdf_id: int, chat_provider: BaseAIProvider, count: int = 10) -> str:
    text = _document_text(pdf_id)
    prompt = f"Document:\n{text}\n\nGenerate {count} interview-style questions (with brief ideal answers) based on this material, in Markdown."
    return chat_provider.generate(prompt, temperature=0.5)


def analyze_difficulty(pdf_id: int, chat_provider: BaseAIProvider) -> dict:
    text = _document_text(pdf_id)
    prompt = (
        f"Document:\n{text}\n\n"
        'Assess this document. Respond ONLY with JSON: {"level": "beginner|intermediate|advanced", '
        '"reasoning": "short explanation", "estimated_study_minutes": number}'
    )
    raw = chat_provider.generate(prompt, system_instruction="You output only valid JSON.", temperature=0.2)
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        return {"level": "unknown", "reasoning": "Could not analyze.", "estimated_study_minutes": 30}


def extract_topics_and_keywords(pdf_id: int, chat_provider: BaseAIProvider) -> dict:
    text = _document_text(pdf_id)
    prompt = (
        f"Document:\n{text}\n\n"
        'Respond ONLY with JSON: {"topics": ["...", "..."], "keywords": ["...", "..."]}. '
        "Max 8 topics, max 15 keywords."
    )
    raw = chat_provider.generate(prompt, system_instruction="You output only valid JSON.", temperature=0.2)
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        return {"topics": [], "keywords": []}


def generate_learning_objectives(pdf_id: int, chat_provider: BaseAIProvider) -> str:
    text = _document_text(pdf_id)
    prompt = f"Document:\n{text}\n\nWrite 5-8 clear learning objectives (starting with action verbs like 'Explain', 'Identify', 'Apply') a student should achieve after studying this, in Markdown bullet list."
    return chat_provider.generate(prompt, temperature=0.3)
