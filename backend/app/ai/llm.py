"""LLM client.

Primary: OpenAI chat completions (used automatically when an API key is set).
Fallback: a deterministic local generator so FAQ/recommendation/analytics
narratives still return sensible, well-formed output offline. Both expose the
same methods, so callers never branch on provider.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("app.ai.llm")


class LLMClient:
    def __init__(self) -> None:
        self.enabled = settings.llm_enabled
        self.model = settings.llm_model
        self._client = None
        if self.enabled:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {
                    "api_key": settings.resolved_llm_api_key,
                    "timeout": settings.openai_timeout_seconds,
                }
                if settings.llm_base_url:
                    kwargs["base_url"] = settings.llm_base_url
                self._client = OpenAI(**kwargs)
            except Exception as exc:  # pragma: no cover
                logger.warning("OpenAI client init failed, using local fallback: %s", exc)
                self.enabled = False

    @property
    def provider(self) -> str:
        return "openai" if (self.enabled and self._client) else "local"

    def complete(self, system: str, user: str, *, temperature: float = 0.3) -> str:
        if self.enabled and self._client is not None:
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                logger.warning("OpenAI chat failed, using local fallback: %s", exc)
        return self._local_complete(system, user)

    def complete_json(self, system: str, user: str, *, temperature: float = 0.2) -> Any:
        """Return parsed JSON. Falls back to local structured output."""
        if self.enabled and self._client is not None:
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system + " Respond ONLY with valid JSON."},
                        {"role": "user", "content": user},
                    ],
                )
                content = resp.choices[0].message.content or "{}"
                return json.loads(content)
            except Exception as exc:
                logger.warning("OpenAI JSON chat failed, using local fallback: %s", exc)
        return self._local_json(system, user)

    # ---------------- Local deterministic fallbacks ----------------
    def _local_complete(self, system: str, user: str) -> str:
        return (
            "This explanation was generated locally because no LLM API key is "
            "configured. Based on the provided information: " + user[:400]
        )

    def _local_json(self, system: str, user: str) -> Any:
        # Used for recommendation extra suggestions + analytics narrative/chart.
        if "recommend" in system.lower() or "suggest" in system.lower():
            return {"suggestions": _local_book_suggestions(user)}
        if "analytics" in system.lower() or "narrative" in system.lower():
            return {
                "narrative": (
                    "Generated locally (no LLM key configured). The metrics below "
                    "are computed deterministically in Python and are exact."
                )
            }
        return {}


def _local_book_suggestions(query: str) -> list[dict]:
    """A tiny built-in catalog of well-known titles keyed loosely by topic, so
    the 'LLM extra suggestions' path returns real, plausible books offline."""
    q = query.lower()
    buckets: dict[str, list[dict]] = {
        "generative ai": [
            {"book_name": "Deep Learning", "author": "Ian Goodfellow, Yoshua Bengio, Aaron Courville", "description": "Foundational textbook covering the theory and practice of deep neural networks."},
            {"book_name": "Generative Deep Learning", "author": "David Foster", "description": "Hands-on guide to building generative models such as VAEs, GANs and transformers."},
        ],
        "machine learning": [
            {"book_name": "Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow", "author": "Aurélien Géron", "description": "Practical end-to-end guide to modern machine learning."},
            {"book_name": "Pattern Recognition and Machine Learning", "author": "Christopher M. Bishop", "description": "Rigorous introduction to statistical machine learning methods."},
        ],
        "python": [
            {"book_name": "Fluent Python", "author": "Luciano Ramalho", "description": "Deep dive into writing idiomatic, effective Python."},
            {"book_name": "Python Crash Course", "author": "Eric Matthes", "description": "Beginner-friendly project-based introduction to Python."},
        ],
        "data": [
            {"book_name": "Designing Data-Intensive Applications", "author": "Martin Kleppmann", "description": "How modern data systems are built, from storage to distributed processing."},
            {"book_name": "Python for Data Analysis", "author": "Wes McKinney", "description": "Data wrangling with pandas, NumPy and Jupyter."},
        ],
    }
    for key, books in buckets.items():
        if any(w in q for w in key.split()):
            return books
    # generic fallback
    return [
        {"book_name": "The Pragmatic Programmer", "author": "Andrew Hunt, David Thomas", "description": "Timeless advice on software craftsmanship."},
        {"book_name": "Clean Code", "author": "Robert C. Martin", "description": "Principles and practices for writing readable, maintainable code."},
    ]


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
