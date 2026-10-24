
"""LLM client.

Primary: Google Gemini API.
Fallback: deterministic local generator for offline FAQ,
recommendations, and analytics narratives.

Both providers expose the same methods, so callers never
need to branch on the provider.
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
        self.model = getattr(
            settings, "llm_model", "gemini-2.5-flash"
        )
        self._client = None

        if self.enabled:
            try:
                from google import genai

                api_key = (
                    getattr(settings, "resolved_llm_api_key", None)
                    or getattr(settings, "llm_api_key", None)
                )

                if not api_key:
                    raise ValueError(
                        "Gemini API key is missing. "
                        "Configure GEMINI_API_KEY or LLM_API_KEY."
                    )

                self._client = genai.Client(api_key=api_key)

            except Exception as exc:
                logger.warning(
                    "Gemini client initialization failed; "
                    "using local fallback: %s",
                    exc,
                )
                self.enabled = False

    @property
    def provider(self) -> str:
        if self.enabled and self._client is not None:
            return "gemini"
        return "local"

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
    ) -> str:
        """Generate a text response using Gemini or local fallback."""

        if self.enabled and self._client is not None:
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config={
                        "system_instruction": system,
                        "temperature": temperature,
                    },
                )

                return (response.text or "").strip()

            except Exception as exc:
                logger.warning(
                    "Gemini text generation failed; "
                    "using local fallback: %s",
                    exc,
                )

        return self._local_complete(system, user)

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
    ) -> Any:
        """Generate and parse JSON, falling back locally on failure."""

        if self.enabled and self._client is not None:
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config={
                        "system_instruction": (
                            system + "\nReturn only valid JSON."
                        ),
                        "response_mime_type": "application/json",
                        "temperature": temperature,
                    },
                )

                content = response.text or "{}"
                return json.loads(content)

            except Exception as exc:
                logger.warning(
                    "Gemini JSON generation failed; "
                    "using local fallback: %s",
                    exc,
                )

        return self._local_json(system, user)

    # ---------------- Local deterministic fallbacks ----------------

    def _local_complete(self, system: str, user: str) -> str:
        return (
            "This explanation was generated locally because "
            "the LLM API is unavailable. "
            "Based on the provided information: "
            + user[:400]
        )

    def _local_json(self, system: str, user: str) -> Any:
        """Local structured responses for supported use cases."""

        system_lower = system.lower()

        if "recommend" in system_lower or "suggest" in system_lower:
            return {
                "suggestions": _local_book_suggestions(user)
            }

        if "analytics" in system_lower or "narrative" in system_lower:
            return {
                "narrative": (
                    "Generated locally because the LLM API is "
                    "unavailable. The metrics below are computed "
                    "deterministically in Python."
                )
            }

        return {}


def _local_book_suggestions(query: str) -> list[dict]:
    """Return a small catalog of book recommendations offline."""

    q = query.lower()

    buckets: dict[str, list[dict]] = {
        "generative ai": [
            {
                "book_name": "Deep Learning",
                "author": (
                    "Ian Goodfellow, Yoshua Bengio, "
                    "Aaron Courville"
                ),
                "description": (
                    "Foundational textbook covering deep neural networks."
                ),
            },
            {
                "book_name": "Generative Deep Learning",
                "author": "David Foster",
                "description": (
                    "Practical guide to VAEs, GANs, and transformers."
                ),
            },
        ],
        "machine learning": [
            {
                "book_name": (
                    "Hands-On Machine Learning with "
                    "Scikit-Learn, Keras & TensorFlow"
                ),
                "author": "Aurélien Géron",
                "description": (
                    "Practical end-to-end guide to machine learning."
                ),
            },
            {
                "book_name": (
                    "Pattern Recognition and Machine Learning"
                ),
                "author": "Christopher M. Bishop",
                "description": (
                    "Statistical machine learning methods."
                ),
            },
        ],
        "python": [
            {
                "book_name": "Fluent Python",
                "author": "Luciano Ramalho",
                "description": (
                    "Writing idiomatic and effective Python."
                ),
            },
            {
                "book_name": "Python Crash Course",
                "author": "Eric Matthes",
                "description": (
                    "Project-based introduction to Python."
                ),
            },
        ],
        "data": [
            {
                "book_name": "Designing Data-Intensive Applications",
                "author": "Martin Kleppmann",
                "description": (
                    "Storage systems and distributed data processing."
                ),
            },
            {
                "book_name": "Python for Data Analysis",
                "author": "Wes McKinney",
                "description": (
                    "Data analysis with pandas and NumPy."
                ),
            },
        ],
    }

    for key, books in buckets.items():
        if any(word in q for word in key.split()):
            return books

    return [
        {
            "book_name": "The Pragmatic Programmer",
            "author": "Andrew Hunt, David Thomas",
            "description": (
                "Advice on software craftsmanship."
            ),
        },
        {
            "book_name": "Clean Code",
            "author": "Robert C. Martin",
            "description": (
                "Principles for readable, maintainable code."
            ),
        },
    ]


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm

    if _llm is None:
        _llm = LLMClient()

    return _llm
