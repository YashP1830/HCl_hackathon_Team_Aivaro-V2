
"""
Recommendation service.

Flow:
1. Validate the query and requested number of recommendations.
2. Search the local catalog using embeddings and vector search.
3. Fetch book records and stock information from the database.
4. Search Google through SerpAPI for additional book candidates.
5. Extract candidate titles, authors, and descriptions from search results.
6. Deduplicate candidates against existing recommendations.
7. Match external candidates against the database.
8. Set library_status and book_id using database records only.
9. Return a consistent RecommendationResponse.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import serpapi
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embeddings
from app.ai.vector_store import search_books
from app.core.config import settings
from app.repositories import repositories as repo
from app.schemas.schemas import (
    RecommendationItem,
    RecommendationResponse,
)

logger = logging.getLogger("app.ai.recommendations")

AUTHOR_FALLBACK = "Author not confirmed"
DESCRIPTION_FALLBACK = "No description available."


# -------------------------------------------------------------------
# Normalization and database helpers
# -------------------------------------------------------------------

def _norm(value: str | None) -> str:
    """Normalize text for case-insensitive comparison."""
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        (value or "").lower(),
    ).strip()


def _dedupe_key(name: str, author: str) -> str:
    """Build a normalized title/author key."""
    return f"{_norm(name)}|{_norm(author)}"


def _status_for_book(book: Any) -> str:
    """
    Calculate availability from the database.

    Never trust external search results for stock information.
    """
    stock = getattr(book, "stock_quantity", 0) or 0

    if stock > 0:
        return "in_library_available"

    return "in_library_out_of_stock"


# -------------------------------------------------------------------
# SerpAPI configuration
# -------------------------------------------------------------------

def _get_serpapi_key() -> str | None:
    """Read the SerpAPI key from application settings or environment."""

    return (
        getattr(settings, "serpapi_api_key", None)
        or os.getenv("SERPAPI_API_KEY")
        or os.getenv("SERPAPI_KEY")
    )


# -------------------------------------------------------------------
# Google search-result parsing
# -------------------------------------------------------------------

_SITE_SUFFIX_PATTERN = re.compile(
    r"\s+(?:\||–|—|-)\s+"
    r"(?:Goodreads|Amazon(?:\.com)?|Google Books|"
    r"WorldCat|Barnes\s*&\s*Noble|Bookshop\.org)"
    r"\b.*$",
    flags=re.IGNORECASE,
)

_LISTING_TITLE_PATTERNS = (
    "best books about",
    "best books on",
    "top 10 books",
    "top books about",
    "top books on",
    "books you should read",
    "reading list",
    "book recommendations",
    "books similar to",
    "list of books",
)


def _clean_search_title(title: str) -> str:
    """Remove common publisher/site suffixes without truncating subtitles."""

    title = (title or "").strip()
    title = _SITE_SUFFIX_PATTERN.sub("", title)
    return title.strip(" \t\r\n-|–—")


def _extract_author(title: str, snippet: str) -> str:
    """
    Extract an author only when the search result provides a plausible name.

    Search result metadata is not guaranteed to contain an author.
    If extraction is uncertain, return an empty string and let the
    database matching step determine whether the title is in the catalog.
    """

    patterns = [
        # Example: "A Book Title by Jane Smith"
        re.compile(
            r"\bby\s+"
            r"([A-Z][A-Za-z.'’\-]+"
            r"(?:\s+(?:[A-Z][A-Za-z.'’\-]+|and|&)){0,5})"
            r"(?=\s*(?:\||–|—|-|:|,|$))"
        ),
        # Example: "Author: Jane Smith"
        re.compile(
            r"\b(?:author|written by)\s*[:\-]\s*"
            r"([A-Z][A-Za-z.'’\-]+"
            r"(?:\s+[A-Z][A-Za-z.'’\-]+){0,4})"
        ),
    ]

    for text in (title, snippet):
        for pattern in patterns:
            match = pattern.search(text or "")

            if match:
                author = match.group(1).strip(" ,.-")
                if author:
                    return author

    return ""


# -------------------------------------------------------------------
# External book search using SerpAPI
# -------------------------------------------------------------------

def _search_external_books(
    query: str,
    n: int,
    already: list[str],
) -> list[dict[str, str]]:
    """
    Search Google via SerpAPI for additional book candidates.

    Returns dictionaries containing:
        book_name
        author
        description

    This function does not assign library availability or database IDs.
    """

    query = (query or "").strip()

    if not query or n <= 0:
        return []

    api_key = _get_serpapi_key()

    if not api_key:
        logger.warning(
            "SERPAPI_API_KEY is not configured; "
            "skipping external book search."
        )
        return []

    try:
        client = serpapi.Client(
            api_key=api_key,
            timeout=15,
        )

        results = client.search(
            engine="google",
            q=f"books about {query} book author",
            hl="en",
            gl="in",
        )

        organic_results = results.get("organic_results", []) or []

        existing_titles = {
            _norm(title)
            for title in already
            if title
        }

        candidates: list[dict[str, str]] = []
        seen_titles: set[str] = set()

        for result in organic_results:
            raw_title = result.get("title", "")
            snippet = (
                result.get("snippet", "")
                or result.get("snippet_highlighted_words", "")
            )

            # Some search result fields may not be plain strings.
            if not isinstance(raw_title, str):
                continue

            if not isinstance(snippet, str):
                snippet = ""

            title = _clean_search_title(raw_title)

            if not title:
                continue

            title_key = _norm(title)

            if not title_key:
                continue

            # Do not treat obvious book-list articles as individual books.
            title_lower = title.lower()

            if any(
                phrase in title_lower
                for phrase in _LISTING_TITLE_PATTERNS
            ):
                continue

            # Avoid results already present in the recommendation list.
            if title_key in existing_titles:
                continue

            if title_key in seen_titles:
                continue

            author = _extract_author(title, snippet)

            description = snippet.strip() or DESCRIPTION_FALLBACK

            candidates.append(
                {
                    "book_name": title,
                    "author": author,
                    "description": description,
                }
            )

            seen_titles.add(title_key)

            if len(candidates) >= n:
                break

        logger.info(
            "SerpAPI returned %d external book candidates for query=%r",
            len(candidates),
            query,
        )

        return candidates

    except Exception:
        # External search failure must not break the recommendation API.
        logger.exception(
            "SerpAPI book search failed for query=%r",
            query,
        )
        return []


# -------------------------------------------------------------------
# Main recommendation service
# -------------------------------------------------------------------

def recommend_books(
    db: Session,
    query: str,
    top_k: int = 5,
) -> RecommendationResponse:
    """
    Combine local vector-search matches with external search candidates.

    Database values are authoritative for all books that match the
    library catalog. External results never determine stock quantities
    or invent database IDs.
    """

    query = (query or "").strip()

    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 5

    top_k = max(0, top_k)

    if not query or top_k == 0:
        return RecommendationResponse(
            query=query,
            recommendations=[],
        )

    items: list[RecommendationItem] = []
    seen_titles: set[str] = set()
    seen_keys: set[str] = set()

    # ---------------------------------------------------------------
    # 1. Search the local catalog using vector search
    # ---------------------------------------------------------------

    try:
        query_vector = get_embeddings().embed(query)

        hits = search_books(
            db,
            query_vector,
            top_k=top_k,
        )

    except Exception:
        logger.exception(
            "Vector search failed; continuing with SerpAPI."
        )
        hits = []

    catalog_titles: list[str] = []

    for hit in hits:
        try:
            book = repo.get_book(db, hit.book_id)
        except Exception:
            logger.exception(
                "Failed to fetch catalog book_id=%s",
                getattr(hit, "book_id", None),
            )
            continue

        if not book:
            continue

        title = (getattr(book, "title", None) or "").strip()

        if not title:
            continue

        author = (
            getattr(book, "author", None) or AUTHOR_FALLBACK
        ).strip()

        title_key = _norm(title)
        dedupe_key = _dedupe_key(title, author)

        if title_key in seen_titles or dedupe_key in seen_keys:
            continue

        seen_titles.add(title_key)
        seen_keys.add(dedupe_key)
        catalog_titles.append(title)

        items.append(
            RecommendationItem(
                book_name=title,
                author=author,
                description=(
                    getattr(book, "description", None)
                    or DESCRIPTION_FALLBACK
                ),
                library_status=_status_for_book(book),
                book_id=book.id,
            )
        )

        if len(items) >= top_k:
            return RecommendationResponse(
                query=query,
                recommendations=items[:top_k],
            )

    # ---------------------------------------------------------------
    # 2. Find additional books through SerpAPI
    # ---------------------------------------------------------------

    remaining = max(0, top_k - len(items))

    if remaining == 0:
        return RecommendationResponse(
            query=query,
            recommendations=items[:top_k],
        )

    suggestions = _search_external_books(
        query=query,
        n=remaining + 3,
        already=catalog_titles,
    )

    # ---------------------------------------------------------------
    # 3. Deduplicate, match against DB, and construct response items
    # ---------------------------------------------------------------

    for suggestion in suggestions:
        name = (
            suggestion.get("book_name") or ""
        ).strip()

        raw_author = (
            suggestion.get("author") or ""
        ).strip()

        description = (
            suggestion.get("description") or ""
        ).strip() or DESCRIPTION_FALLBACK

        if not name:
            continue

        title_key = _norm(name)

        if not title_key or title_key in seen_titles:
            continue

        candidate_key = _dedupe_key(name, raw_author)

        if candidate_key in seen_keys:
            continue

        # Search the database before treating a result as external.
        try:
            matched = _match_catalog(
                db=db,
                name=name,
                author=raw_author,
            )
        except Exception:
            logger.exception(
                "Database matching failed for external title=%r",
                name,
            )
            matched = None

        if matched is not None:
            matched_title = (
                getattr(matched, "title", None) or name
            ).strip()

            matched_author = (
                getattr(matched, "author", None)
                or AUTHOR_FALLBACK
            ).strip()

            matched_title_key = _norm(matched_title)
            matched_key = _dedupe_key(
                matched_title,
                matched_author,
            )

            # A previously emitted catalog book should not appear twice.
            if (
                matched_title_key in seen_titles
                or matched_key in seen_keys
            ):
                continue

            item = RecommendationItem(
                book_name=matched_title,
                author=matched_author,
                description=(
                    getattr(matched, "description", None)
                    or description
                ),
                library_status=_status_for_book(matched),
                book_id=matched.id,
            )

            seen_titles.add(matched_title_key)
            seen_keys.add(matched_key)

        else:
            # No authoritative database record was found.
            # Do not invent IDs or claim that the library stocks it.
            external_author = raw_author or AUTHOR_FALLBACK

            item = RecommendationItem(
                book_name=name,
                author=external_author,
                description=description,
                library_status="not_in_library",
                book_id=None,
            )

            seen_titles.add(title_key)
            seen_keys.add(candidate_key)

        items.append(item)

        if len(items) >= top_k:
            break

    return RecommendationResponse(
        query=query,
        recommendations=items[:top_k],
    )


# -------------------------------------------------------------------
# Catalog matching
# -------------------------------------------------------------------

def _match_catalog(
    db: Session,
    name: str,
    author: str,
):
    """
    Match an external result against the local database.

    Matching policy:
    - Titles must match after normalization.
    - If the author is known, it must also match the database author.
    - If the author is unknown, an exact normalized title match is
      sufficient to retrieve authoritative database information.
    - Do not match a known, conflicting author just because the title
      is the same.
    """

    target_title = _norm(name)

    if not target_title:
        return None

    target_author = _norm(author)

    if target_author == _norm(AUTHOR_FALLBACK):
        target_author = ""

    # This small-catalog approach matches the existing repository API.
    books, _ = repo.list_books(
        db,
        q=None,
        page=1,
        page_size=1000,
    )

    for book in books:
        book_title = _norm(
            getattr(book, "title", None)
        )

        if book_title != target_title:
            continue

        book_author = _norm(
            getattr(book, "author", None)
        )

        # Author was not provided by search, so use the exact title match.
        if not target_author:
            return book

        # If the DB author is missing, the exact title can still be useful.
        if not book_author:
            return book

        # Require a reasonably consistent author match.
        if (
            target_author == book_author
            or target_author in book_author
            or book_author in target_author
        ):
            return book

    return None
