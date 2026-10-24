"""Gemini LLM client with a local fallback."""

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
                from google import genai

                self._client = genai.Client(
                    api_key=settings.resolved_gemini_api_key
                )

            except Exception as exc:
                logger.warning(
                    "Gemini client initialization failed; "
                    "using local fallback: %s",
                    exc,
                )
                self.enabled = False

    @property
    def provider(self) -> str:
        return (
            "gemini"
            if self.enabled and self._client is not None
            else "local"
        )

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
    ) -> str:
        """Generate normal text."""

        if self.enabled and self._client is not None:
            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=temperature,
                    ),
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
        """Generate JSON and parse it into a Python object."""

        if self.enabled and self._client is not None:
            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=(
                            system + "\nReturn only valid JSON."
                        ),
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                )

                return json.loads(response.text or "{}")

            except Exception as exc:
                logger.warning(
                    "Gemini JSON generation failed; "
                    "using local fallback: %s",
                    exc,
                )

        return self._local_json(system, user)

    def _local_complete(self, system: str, user: str) -> str:
        return (
            "This explanation was generated locally because Gemini "
            "is unavailable. Based on the provided information: "
            + user[:400]
        )

    def _local_json(self, system: str, user: str) -> Any:
        system_lower = system.lower()

        if (
            "analytics" in system_lower
            or "narrative" in system_lower
        ):
            return {
                "narrative": (
                    "Generated locally because Gemini is unavailable. "
                    "The metrics below are computed deterministically "
                    "in Python."
                )
            }

        if (
            "recommend" in system_lower
            or "suggest" in system_lower
        ):
            return {"suggestions": []}

        return {}


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm

    if _llm is None:
        _llm = LLMClient()

    return _llm