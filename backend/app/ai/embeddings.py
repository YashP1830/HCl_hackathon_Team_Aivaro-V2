"""Embedding provider.

Primary: OpenAI ``text-embedding-3-small`` (used automatically when an API key
is configured). Fallback: a deterministic, dependency-free local embedding so
semantic search still works offline on a fresh machine. Both paths return a
vector of exactly ``settings.embedding_dimension`` floats, so documents and
queries always share the same dimension within a run.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re

from app.core.config import settings

logger = logging.getLogger("app.ai.embeddings")

_WORD_RE = re.compile(r"[a-z0-9]+")


def _local_embed(text: str, dim: int) -> list[float]:
    """Deterministic hashing embedding (bag of word + char-trigram hashes)."""
    vec = [0.0] * dim
    text = (text or "").lower()
    tokens = _WORD_RE.findall(text)
    # unigrams
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    # char trigrams for fuzzy overlap
    joined = " ".join(tokens)
    for i in range(len(joined) - 2):
        tri = joined[i : i + 3]
        h = int(hashlib.md5(tri.encode()).hexdigest(), 16)
        vec[h % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class EmbeddingProvider:
    def __init__(self) -> None:
        self.dim = settings.embedding_dimension
        self.remote = settings.embeddings_remote_enabled
        self.model = settings.embedding_model if self.remote else "local-hash-v1"
        self._client = None
        if self.remote:
            try:
                from openai import OpenAI

                kwargs = {"api_key": settings.resolved_llm_api_key, "timeout": settings.openai_timeout_seconds}
                if settings.llm_base_url:
                    kwargs["base_url"] = settings.llm_base_url
                self._client = OpenAI(**kwargs)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("OpenAI embedding client init failed, using local fallback: %s", exc)
                self.remote = False
                self.model = "local-hash-v1"

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.remote and self._client is not None:
            try:
                resp = self._client.embeddings.create(
                    model=self.model,
                    input=[t or " " for t in texts],
                    dimensions=self.dim,
                )
                return [d.embedding for d in resp.data]
            except Exception as exc:
                # Never crash a request because a remote call failed; degrade.
                logger.warning("OpenAI embedding call failed, using local fallback: %s", exc)
        return [_local_embed(t, self.dim) for t in texts]


_provider: EmbeddingProvider | None = None


def get_embeddings() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = EmbeddingProvider()
    return _provider


def build_book_text(*, title: str, author: str, description: str, genre: str, publisher: str) -> str:
    """Stable descriptive text for a book embedding. Must NOT include stock."""
    parts = [title, author, genre, publisher, description]
    return " \n".join(p for p in parts if p)
