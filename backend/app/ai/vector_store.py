"""Portable vector similarity search.

Reads stored embeddings (JSON) from the DB and ranks them against a query
vector with cosine similarity using NumPy. Works identically on SQLite and
PostgreSQL. If PostgreSQL + pgvector is present you could swap this for a native
query, but the Python path keeps the app fully functional everywhere.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from app.repositories import repositories as repo


@dataclass
class VectorHit:
    book_id: str
    score: float


def _to_array(json_str: str) -> np.ndarray:
    return np.asarray(json.loads(json_str), dtype=np.float32)


def search_books(db: Session, query_vector: list[float], top_k: int, min_score: float = 0.15) -> list[VectorHit]:
    rows = repo.all_embeddings(db)
    if not rows:
        return []
    q = np.asarray(query_vector, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []
    q = q / q_norm

    hits: list[VectorHit] = []
    for row in rows:
        try:
            v = _to_array(row.embedding)
        except Exception:
            continue
        if v.shape != q.shape:
            continue
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            continue
        score = float(np.dot(q, v / v_norm))
        if score >= min_score:
            hits.append(VectorHit(book_id=row.book_id, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
