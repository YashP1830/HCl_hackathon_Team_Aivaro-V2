"""LangChain-backed LLM facade retaining existing service method signatures."""
from __future__ import annotations

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
                from langchain_openai import ChatOpenAI
                kwargs: dict[str, Any] = {
                    "api_key": settings.resolved_llm_api_key,
                    "model": self.model,
                    "timeout": settings.openai_timeout_seconds,
                    "max_retries": 2,
                }
                if settings.llm_base_url:
                    kwargs["base_url"] = settings.llm_base_url
                self._client = ChatOpenAI(**kwargs)
            except Exception as exc:
                logger.warning("LangChain chat init failed; using local fallback: %s", exc)
                self.enabled = False

    @property
    def provider(self) -> str:
        return "openai" if self.enabled and self._client is not None else "local"

    def complete(self, system: str, user: str, *, temperature: float = 0.3) -> str:
        if self.enabled and self._client is not None:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                result = self._client.bind(temperature=temperature).invoke([
                    SystemMessage(content=system), HumanMessage(content=user)
                ])
                content = result.content
                if isinstance(content, str):
                    return content.strip()
                return "".join(b.get("text", "") for b in content if isinstance(b, dict)).strip()
            except Exception as exc:
                logger.warning("LangChain chat call failed; using local fallback: %s", exc)
        return self._local_complete(system, user)

    def complete_json(self, system: str, user: str, *, temperature: float = 0.2) -> Any:
        if self.enabled and self._client is not None:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                from langchain_core.output_parsers import JsonOutputParser
                model = self._client.bind(temperature=temperature, response_format={"type": "json_object"})
                result = model.invoke([
                    SystemMessage(content=system + " Respond ONLY with valid JSON."),
                    HumanMessage(content=user),
                ])
                content = result.content
                if not isinstance(content, str):
                    content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
                return JsonOutputParser().parse(content or "{}")
            except Exception as exc:
                logger.warning("LangChain JSON call failed; using local fallback: %s", exc)
        return self._local_json(system, user)

    def _local_complete(self, system: str, user: str) -> str:
        return ("This explanation was generated locally because no LLM API key is "
                "configured. Based on the provided information: " + user[:400])

    def _local_json(self, system: str, user: str) -> Any:
        if "recommend" in system.lower() or "suggest" in system.lower():
            return {"suggestions": _local_book_suggestions(user)}
        if "analytics" in system.lower() or "narrative" in system.lower():
            return {"narrative": "Generated locally (no LLM key configured). Metrics are computed deterministically in Python."}
        return {}


def _local_book_suggestions(query: str) -> list[dict]:
    q = query.lower()
    buckets: dict[str, list[dict]] = {
        "generative ai": [
            {"book_name": "Deep Learning", "author": "Ian Goodfellow, Yoshua Bengio, Aaron Courville", "description": "Foundational textbook covering deep neural networks."},
            {"book_name": "Generative Deep Learning", "author": "David Foster", "description": "Hands-on guide to VAEs, GANs and transformers."}],
        "machine learning": [
            {"book_name": "Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow", "author": "Aurélien Géron", "description": "Practical end-to-end guide to modern machine learning."},
            {"book_name": "Pattern Recognition and Machine Learning", "author": "Christopher M. Bishop", "description": "Rigorous introduction to statistical machine learning."}],
        "python": [
            {"book_name": "Fluent Python", "author": "Luciano Ramalho", "description": "Writing idiomatic, effective Python."},
            {"book_name": "Python Crash Course", "author": "Eric Matthes", "description": "Project-based introduction to Python."}],
        "data": [
            {"book_name": "Designing Data-Intensive Applications", "author": "Martin Kleppmann", "description": "Reliable and scalable data systems."},
            {"book_name": "Python for Data Analysis", "author": "Wes McKinney", "description": "Data wrangling with pandas and NumPy."}],
    }
    for key, books in buckets.items():
        if any(word in q for word in key.split()):
            return books
    return [
        {"book_name": "The Pragmatic Programmer", "author": "Andrew Hunt, David Thomas", "description": "Advice on software craftsmanship."},
        {"book_name": "Clean Code", "author": "Robert C. Martin", "description": "Principles for readable, maintainable code."}]


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
