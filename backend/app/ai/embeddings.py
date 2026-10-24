"""LangChain-backed embedding provider, with the original offline fallback."""
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
    tokens = _WORD_RE.findall((text or "").lower())
    for tok in tokens:
        vec[int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim] += 1.0
    joined = " ".join(tokens)
    for i in range(len(joined) - 2):
        vec[int(hashlib.md5(joined[i:i + 3].encode()).hexdigest(), 16) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
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
                from langchain_openai import OpenAIEmbeddings
                kwargs = {
                    "api_key": settings.resolved_llm_api_key,
                    "model": self.model,
                    "dimensions": self.dim,
                    "request_timeout": settings.openai_timeout_seconds,
                    "max_retries": 2,
                }
                if settings.llm_base_url:
                    kwargs["base_url"] = settings.llm_base_url
                self._client = OpenAIEmbeddings(**kwargs)
            except Exception as exc:
                logger.warning("LangChain embeddings init failed; using local fallback: %s", exc)
                self.remote = False
                self.model = "local-hash-v1"

    def embed(self, text: str) -> list[float]:
        if self.remote and self._client is not None:
            try:
                return self._client.embed_query(text or " ")
            except Exception as exc:
                logger.warning("LangChain embedding call failed; using local fallback: %s", exc)
        return _local_embed(text, self.dim)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.remote and self._client is not None:
            try:
                return self._client.embed_documents([t or " " for t in texts])
            except Exception as exc:
                logger.warning("LangChain batch embedding failed; using local fallback: %s", exc)
        return [_local_embed(t, self.dim) for t in texts]


_provider: EmbeddingProvider | None = None


def get_embeddings() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = EmbeddingProvider()
    return _provider


def build_book_text(*, title: str, author: str, description: str, genre: str, publisher: str) -> str:
    """Stable descriptive text for a book embedding. Must NOT include stock."""
    return " \n".join(p for p in [title, author, genre, publisher, description] if p)
