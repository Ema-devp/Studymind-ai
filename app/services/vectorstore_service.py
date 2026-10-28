"""
Per-document FAISS vector store.

Each PDF gets its own flat L2 index on disk under INDEX_FOLDER, named by
pdf id (e.g. indexes/pdf_42.index). Keeping one index per document (rather
than one huge global index) keeps search fast and makes deleting a PDF a
simple file removal.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import faiss

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self, index_folder: str, dimensions: int):
        self.index_folder = index_folder
        self.dimensions = dimensions
        os.makedirs(index_folder, exist_ok=True)

    def _index_path(self, pdf_id: int) -> str:
        return os.path.join(self.index_folder, f"pdf_{pdf_id}.index")

    def build_index(self, pdf_id: int, vectors: list[list[float]]) -> str:
        """Builds a new FAISS index from scratch for a document and saves it."""
        matrix = np.array(vectors, dtype="float32")
        index = faiss.IndexFlatIP(matrix.shape[1])  # cosine similarity via normalized inner product
        faiss.normalize_L2(matrix)
        index.add(matrix)
        path = self._index_path(pdf_id)
        faiss.write_index(index, path)
        logger.info("Built FAISS index for pdf_id=%s with %d vectors -> %s", pdf_id, len(vectors), path)
        return path

    def load_index(self, pdf_id: int):
        path = self._index_path(pdf_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"No vector index found for PDF {pdf_id}")
        return faiss.read_index(path)

    def search(self, pdf_id: int, query_vector: list[float], top_k: int = 5):
        """Returns list of (vector_id, similarity_score) sorted best-first."""
        index = self.load_index(pdf_id)
        q = np.array([query_vector], dtype="float32")
        faiss.normalize_L2(q)
        scores, ids = index.search(q, min(top_k, index.ntotal))
        results = []
        for score, vid in zip(scores[0], ids[0]):
            if vid == -1:
                continue
            results.append((int(vid), float(score)))
        return results

    def delete_index(self, pdf_id: int) -> None:
        path = self._index_path(pdf_id)
        if os.path.exists(path):
            os.remove(path)
