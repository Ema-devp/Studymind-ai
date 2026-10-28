"""Text chunk produced from a PDF during processing.

Embeddings themselves live in the FAISS index on disk (see
app/services/vectorstore_service.py); this row keeps the human-readable text
and page metadata so we can display citations, and `vector_id` links it back
to its row inside the FAISS index.
"""
from datetime import datetime

from app import db


class Chunk(db.Model):
    __tablename__ = "chunks"

    id = db.Column(db.Integer, primary_key=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey("pdfs.id"), nullable=False, index=True)

    vector_id = db.Column(db.Integer, nullable=False)  # position inside the FAISS index
    chunk_index = db.Column(db.Integer, nullable=False)  # order within the document
    page_number = db.Column(db.Integer, nullable=True)
    content = db.Column(db.Text, nullable=False)
    token_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("pdf_id", "vector_id", name="uq_chunk_pdf_vector"),
    )

    def __repr__(self):
        return f"<Chunk pdf={self.pdf_id} idx={self.chunk_index} page={self.page_number}>"
