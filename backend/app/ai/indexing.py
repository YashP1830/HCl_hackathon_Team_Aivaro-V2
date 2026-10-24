"""Embedding sync for books (called by the admin book routes via a service).

Contract from KT 4.2 / 5: save the book first, then try to build the vector.
If the vector upsert fails, keep the catalog row and mark embedding 'failed'
(never report indexing ready). Stock-only changes must NOT call this.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.ai.embeddings import build_book_text, get_embeddings
from app.models.models import Book
from app.repositories import repositories as repo

logger = logging.getLogger("app.ai.indexing")


def sync_book_embedding(db: Session, book: Book) -> tuple[str, str | None]:
    """Returns (embedding_status, detail)."""
    text = build_book_text(
        title=book.title,
        author=book.author,
        description=book.description,
        genre=book.genre,
        publisher=book.publisher,
    )
    try:
        emb = get_embeddings()
        vector = emb.embed(text)
        repo.set_embedding(
            db,
            book_id=book.id,
            vector_json=json.dumps(vector),
            text=text,
            model=emb.model,
            dim=emb.dim,
        )
        return "ready", None
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Embedding sync failed for book %s", book.id)
        repo.mark_embedding_failed(db, book.id)
        return "failed", f"Embedding generation failed: {exc}"
