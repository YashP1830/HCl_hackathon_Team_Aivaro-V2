"""Gemini embedding provider.

Primary: Gemini gemini-embedding-001.
Fallback: deterministic local hashing when no Gemini key is configured.

Remote failures raise an exception instead of silently mixing incompatible
vector spaces in the database.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger("app.ai.embeddings")

_WORD_RE = re.compile(r"[a-z0-9]+")


def _local_embed(text: str, dim: int) -> list[float]:
    """Deterministic local hashing embedding."""

    vec = [0.0] * dim
    tokens = _WORD_RE.findall((text or "").lower())

    for token in tokens:
        digest = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[digest % dim] += 1.0

    joined = " ".join(tokens)

    for i in range(len(joined) - 2):
        trigram = joined[i:i + 3]
        digest = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
        vec[digest % dim] += 0.5

    norm = math.sqrt(sum(value * value for value in vec))

    if norm > 0:
        vec = [value / norm for value in vec]

    return vec


def _normalize(values: Any, dim: int) -> list[float]:
    """Validate and normalize a Gemini vector."""

    vector = [float(value) for value in values]

    if len(vector) != dim:
        raise ValueError(
            f"Gemini returned {len(vector)} dimensions; expected {dim}."
        )

    norm = math.sqrt(sum(value * value for value in vector))

    if norm == 0:
        raise ValueError("Gemini returned a zero embedding.")

    return [value / norm for value in vector]


class EmbeddingProvider:
    def __init__(self) -> None:
        self.dim = settings.embedding_dimension
        self.remote = settings.embeddings_remote_enabled
        self.model = (
            settings.embedding_model
            if self.remote
            else "local-hash-v1"
        )
        self._client = None

        if self.remote:
            try:
                from google import genai

                self._client = genai.Client(
                    api_key=settings.resolved_gemini_api_key
                )

            except Exception as exc:
                logger.warning(
                    "Gemini embedding client initialization failed: %s",
                    exc,
                )
                self.remote = False
                self.model = "local-hash-v1"

    def embed(
        self,
        text: str,
        *,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        """Generate one embedding."""

        return self.embed_batch(
            [text],
            task_type=task_type,
        )[0]

    def embed_batch(
        self,
        texts: list[str],
        *,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts."""

        if not texts:
            return []

        if self.remote and self._client is not None:
            try:
                from google.genai import types

                response = self._client.models.embed_content(
                    model=self.model,
                    contents=[text or " " for text in texts],
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.dim,
                    ),
                )

                embeddings = response.embeddings or []

                if len(embeddings) != len(texts):
                    raise ValueError(
                        "Gemini returned a different number of embeddings "
                        "than inputs."
                    )

                return [
                    _normalize(embedding.values or [], self.dim)
                    for embedding in embeddings
                ]

            except Exception:
                logger.exception("Gemini embedding request failed")
                raise

        # Local mode is used when no usable Gemini client was configured.
        return [
            _local_embed(text, self.dim)
            for text in texts
        ]


_provider: EmbeddingProvider | None = None


def get_embeddings() -> EmbeddingProvider:
    global _provider

    if _provider is None:
        _provider = EmbeddingProvider()

    return _provider


def build_book_text(
    *,
    title: str,
    author: str,
    description: str,
    genre: str,
    publisher: str,
) -> str:
    """Stable book metadata used for indexing. Never include stock."""

    parts = [title, author, genre, publisher, description]

    return " \n".join(part for part in parts if part)