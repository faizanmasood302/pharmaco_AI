from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
COLLECTION_NAME = "cpic_knowledge"
SIMILARITY_THRESHOLD = 0.3


class ClinicalVectorStore:
    """ChromaDB-backed semantic search over CPIC knowledge base with deterministic guardrails."""

    def __init__(self) -> None:
        self._collection: Any = None
        self._ready = False

    def _ensure_indexed(self) -> Any:
        if self._ready and self._collection is not None:
            return self._collection
        try:
            client = chromadb.Client(Settings(anonymized_telemetry=False))
            self._collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            count = self._collection.count()
            if count == 0:
                self._index_files()
            self._ready = True
            logger.info("Vector store ready — %d chunks indexed", self._collection.count())
            return self._collection
        except Exception as exc:
            logger.warning("Vector store unavailable, falling back to keyword: %s", exc)
            self._ready = False
            return None

    def _index_files(self) -> None:
        if self._collection is None:
            return
        documents: list[str] = []
        metadatas: list[dict[str, str]] = []
        ids: list[str] = []

        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            parts = [part.strip() for part in re.split(r"\n(?=## |\# )", text) if part.strip()]
            for idx, part in enumerate(parts):
                chunk_id = f"{path.name}:{idx + 1}"
                documents.append(part)
                metadatas.append({"source": path.name, "chunk_id": chunk_id})
                ids.append(chunk_id)

        if documents:
            self._collection.add(documents=documents, metadatas=metadatas, ids=ids)
            logger.info("Indexed %d chunks from %d files", len(documents), len(ids))

    def query(self, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic search with deterministic relevance threshold."""
        start = time.perf_counter()
        collection = self._ensure_indexed()
        if collection is None:
            return []

        try:
            results = collection.query(
                query_texts=[query_text],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("Vector query failed: %s", exc)
            return []

        if not results or not results["documents"] or not results["documents"][0]:
            return []

        hits: list[dict[str, Any]] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1.0 - dist
            if similarity < SIMILARITY_THRESHOLD:
                continue
            hits.append({
                "source": meta.get("source", "unknown"),
                "chunk_id": meta.get("chunk_id", "unknown"),
                "text": doc,
                "similarity": round(similarity, 4),
                "distance": round(dist, 4),
            })

        elapsed = int((time.perf_counter() - start) * 1000)
        logger.info("Vector query '%s' — %d hits in %dms", query_text[:60], len(hits), elapsed)
        return hits


_store: ClinicalVectorStore | None = None


def get_store() -> ClinicalVectorStore:
    global _store
    if _store is None:
        _store = ClinicalVectorStore()
    return _store


def query_clinical_knowledge(
    query_text: str,
    top_k: int = 5,
    min_similarity: float = SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """Query the clinical knowledge base with semantic search + deterministic guardrail.

    Guardrails:
      - Minimum cosine similarity threshold (default 0.3)
      - Results sorted by similarity descending
      - Empty list when no results exceed threshold
    """
    store = get_store()
    results = store.query(query_text, top_k=top_k)
    return [r for r in results if r["similarity"] >= min_similarity]
