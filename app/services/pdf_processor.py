"""
Extracts and chunks text from PDF files using PyMuPDF (fitz).

Pipeline: extract per-page text -> clean whitespace/artifacts -> split into
overlapping chunks sized for good embedding quality (roughly paragraph/
section sized, not single sentences and not whole pages).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class PageText:
    page_number: int  # 1-indexed
    text: str


@dataclass
class TextChunk:
    chunk_index: int
    page_number: int
    content: str


class PDFProcessorError(RuntimeError):
    pass


def extract_pages(file_path: str) -> list[PageText]:
    """Extract raw text per page."""
    pages: list[PageText] = []
    try:
        with fitz.open(file_path) as doc:
            for i, page in enumerate(doc):
                raw = page.get_text("text")
                pages.append(PageText(page_number=i + 1, text=raw))
    except Exception as e:  # noqa: BLE001
        raise PDFProcessorError(f"Could not read PDF: {e}") from e
    return pages


def get_page_count(file_path: str) -> int:
    with fitz.open(file_path) as doc:
        return doc.page_count


def clean_text(text: str) -> str:
    """Normalize whitespace and strip common PDF extraction artifacts."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # de-hyphenate words split across a line break, e.g. "inter-\nnational"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return text.strip()


def chunk_pages(
    pages: list[PageText],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[TextChunk]:
    """
    Splits cleaned page text into overlapping chunks. Chunking is
    paragraph-aware: we accumulate paragraphs until we hit `chunk_size`
    characters, then start a new chunk carrying `chunk_overlap` characters
    of trailing context forward, so retrieval doesn't lose context at
    chunk boundaries.
    """
    chunks: list[TextChunk] = []
    buffer = ""
    buffer_page = None
    idx = 0

    def flush(next_page):
        nonlocal buffer, buffer_page, idx
        if buffer.strip():
            chunks.append(TextChunk(chunk_index=idx, page_number=buffer_page or next_page, content=buffer.strip()))
            idx += 1
        overlap_tail = buffer[-chunk_overlap:] if chunk_overlap else ""
        buffer = overlap_tail

    for page in pages:
        cleaned = clean_text(page.text)
        if not cleaned:
            continue
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
        if not paragraphs:
            paragraphs = [cleaned]

        for para in paragraphs:
            if buffer_page is None:
                buffer_page = page.page_number
            if len(buffer) + len(para) + 1 > chunk_size and buffer.strip():
                flush(page.page_number)
                buffer_page = page.page_number
            buffer = (buffer + "\n\n" + para).strip() if buffer else para

    if buffer.strip():
        chunks.append(TextChunk(chunk_index=idx, page_number=buffer_page or 1, content=buffer.strip()))

    return chunks


def process_pdf(file_path: str, chunk_size: int = 800, chunk_overlap: int = 120) -> list[TextChunk]:
    """Full extract -> clean -> chunk pipeline."""
    pages = extract_pages(file_path)
    if not any(p.text.strip() for p in pages):
        raise PDFProcessorError(
            "No extractable text found. The PDF may be scanned/image-only and "
            "needs OCR, which is not yet enabled in this build."
        )
    return chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
