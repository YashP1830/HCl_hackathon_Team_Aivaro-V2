"""Research-paper search node (KT 4.4 / 6).

Primary: SerpAPI Google Scholar engine (used when SERPAPI_API_KEY is set).
Fallback: a safe, clearly-labelled no-results response -- never fabricated
citations. Only fields actually returned by the provider are populated.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from app.core.config import settings
from app.schemas.schemas import ResearchResponse, ResearchResult

logger = logging.getLogger("app.ai.research")

_SERPAPI_URL = "https://serpapi.com/search.json"


def _parse_year(value) -> Optional[int]:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except (ValueError, TypeError):
        return None


def search_research_papers(topic: str, max_results: int = 5) -> ResearchResponse:
    topic = (topic or "").strip()
    if not topic:
        return ResearchResponse(topic=topic, results=[], note="Empty topic.")

    if not settings.serpapi_enabled:
        return ResearchResponse(
            topic=topic,
            results=[],
            note=(
                "Live Google Scholar search is unavailable because no SERPAPI_API_KEY "
                "is configured. Add one to .env to enable real paper search. No "
                "citations are fabricated."
            ),
        )

    try:
        resp = requests.get(
            _SERPAPI_URL,
            params={
                "engine": "google_scholar",
                "q": topic,
                "num": max(1, min(max_results, 20)),
                "api_key": settings.serpapi_api_key,
            },
            timeout=settings.serpapi_timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("SerpAPI research request failed: %s", exc)
        return ResearchResponse(
            topic=topic,
            results=[],
            note=f"Research search temporarily unavailable ({type(exc).__name__}). Please try again.",
        )

    organic = data.get("organic_results") or []
    results: list[ResearchResult] = []
    seen: set[str] = set()

    for item in organic[:max_results]:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        pub = item.get("publication_info") or {}
        authors = [a.get("name") for a in (pub.get("authors") or []) if a.get("name")]
        summary = pub.get("summary") or ""
        year = _parse_year(_extract_year_from_summary(summary))

        results.append(
            ResearchResult(
                title=title,
                authors=authors,
                year=year,
                snippet=(item.get("snippet") or None),
                url=(item.get("link") or None),
                doi=None,  # SerpAPI Scholar does not reliably return DOI
            )
        )

    note = None if results else "No Google Scholar results found for this topic."
    return ResearchResponse(topic=topic, results=results, note=note)


def _extract_year_from_summary(summary: str) -> Optional[str]:
    import re

    m = re.search(r"(19|20)\d{2}", summary or "")
    return m.group(0) if m else None
