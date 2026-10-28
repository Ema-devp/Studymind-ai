"""
Orchestrates the full "upload -> processed & searchable" pipeline:

    save file -> extract/clean/chunk -> embed -> build FAISS index -> persist
    Chunk rows -> mark PDF as completed.

Called synchronously right after upload in this reference build; in
production this body would be handed to a background worker (Celery/RQ) so
uploads return immediately - see README "Background Processing" notes.
"""
from __future__ import annotations

import logging
import os
import uuid

from werkzeug.utils import secure_filename

from app import db
from app.models.pdf import PDF, ProcessingStatus
from app.models.chunk import Chunk
from app.services import pdf_processor
from app.services.embedding_service import embed_chunks
from app.services.ai_providers.base import BaseAIProvider
from app.services.vectorstore_service import VectorStoreService
from app.utils.helpers import slugify_filename

logger = logging.getLogger(__name__)


def save_uploaded_file(file_storage, upload_folder: str) -> tuple[str, str, int]:
    """Saves the incoming file with a collision-proof name.
    Returns (stored_filename, absolute_path, size_bytes)."""
    original = slugify_filename(secure_filename(file_storage.filename))
    stored_filename = f"{uuid.uuid4().hex}_{original}"
    abs_path = os.path.join(upload_folder, stored_filename)
    file_storage.save(abs_path)
    size = os.path.getsize(abs_path)
    return stored_filename, abs_path, size


def create_pdf_record(user_id: int, title: str, original_filename: str,
                       stored_filename: str, file_path: str, size_bytes: int) -> PDF:
    pdf = PDF(
        user_id=user_id,
        title=title or original_filename,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_path=file_path,
        file_size_bytes=size_bytes,
        processing_status=ProcessingStatus.PENDING,
    )
    db.session.add(pdf)
    db.session.commit()
    return pdf


def process_pdf_pipeline(
    pdf: PDF,
    embedding_provider: BaseAIProvider,
    vectorstore: VectorStoreService,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> None:
    """Runs extraction -> chunking -> embedding -> indexing for one PDF.
    Updates the PDF row's status as it progresses. Safe to call again if it
    previously failed."""
    pdf.processing_status = ProcessingStatus.PROCESSING
    pdf.processing_error = None
    db.session.commit()

    try:
        pdf.page_count = pdf_processor.get_page_count(pdf.file_path)
        chunks = pdf_processor.process_pdf(pdf.file_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            raise pdf_processor.PDFProcessorError("Document produced no usable text chunks.")

        texts = [c.content for c in chunks]
        vectors = embed_chunks(embedding_provider, texts)

        index_path = vectorstore.build_index(pdf.id, vectors)

        # Wipe any previous chunk rows (re-processing case) then insert fresh ones
        Chunk.query.filter_by(pdf_id=pdf.id).delete()
        for vector_id, c in enumerate(chunks):
            db.session.add(Chunk(
                pdf_id=pdf.id,
                vector_id=vector_id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                content=c.content,
                token_count=len(c.content.split()),
            ))

        pdf.chunk_count = len(chunks)
        pdf.index_path = index_path
        pdf.processing_status = ProcessingStatus.COMPLETED
        db.session.commit()
        logger.info("PDF %s processed successfully (%d chunks)", pdf.id, len(chunks))

    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        pdf.processing_status = ProcessingStatus.FAILED
        pdf.processing_error = str(e)
        db.session.commit()
        logger.exception("Processing failed for PDF %s", pdf.id)
        raise


def delete_pdf(pdf: PDF, vectorstore: VectorStoreService) -> None:
    """Removes the DB row (cascades to chunks/chats/etc.), the FAISS index,
    and the uploaded file from disk."""
    vectorstore.delete_index(pdf.id)
    if pdf.file_path and os.path.exists(pdf.file_path):
        os.remove(pdf.file_path)
    db.session.delete(pdf)
    db.session.commit()
