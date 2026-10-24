"""Recommendation service (KT 4.1 / 6).

Flow:
  1. validate query
  2. embed query, search pgvector/portable store for catalog candidates
  3. fetch book rows + current stock from the DB (source of truth)
  4. ask the LLM for extra candidate books (strict book_name/author/description)
  5. normalize + dedupe LLM candidates against catalog matches
  6. set library_status + book_id from the DATABASE, never from the LLM
  7. return the common response shape for every item
"""
from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.ai.embeddings import get_embeddings
from app.ai.llm import get_llm
from app.ai.vector_store import search_books
from app.repositories import repositories as repo
from app.schemas.schemas import RecommendationItem, RecommendationResponse

logger = logging.getLogger("app.ai.recommendations")

AUTHOR_FALLBACK = "Author not confirmed"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _dedupe_key(name: str, author: str) -> str:
    return f"{_norm(name)}|{_norm(author)}"


def _status_for_book(book) -> str:
    return "in_library_available" if book.stock_quantity > 0 else "in_library_out_of_stock"


def recommend_books(db: Session, query: str, top_k: int = 5) -> RecommendationResponse:
    query = (query or "").strip()
    items: list[RecommendationItem] = []
    seen: set[str] = set()

    # --- Catalog matches via vector search ---
    try:
        qvec = get_embeddings().embed(query)
        hits = search_books(db, qvec, top_k=top_k)
    except Exception:
        logger.exception("Vector search failed; returning LLM-only suggestions")
        hits = []

    catalog_titles: list[str] = []
    for hit in hits:
        book = repo.get_book(db, hit.book_id)
        if not book:
            continue
        key = _dedupe_key(book.title, book.author)
        if key in seen:
            continue
        seen.add(key)
        catalog_titles.append(f"{book.title} by {book.author}")
        items.append(
            RecommendationItem(
                book_name=book.title,
                author=book.author or AUTHOR_FALLBACK,
                description=book.description or "No description available.",
                library_status=_status_for_book(book),
                book_id=book.id,
            )
        )

    # --- Extra LLM suggestions (strict fields only) ---
    remaining = max(0, top_k - len(items))
    if remaining > 0:
        try:
            suggestions = _llm_suggestions(query, n=remaining + 2, already=catalog_titles)
        except Exception:
            logger.exception("LLM suggestion step failed; skipping extra suggestions")
            suggestions = []

        for sug in suggestions:
            name = (sug.get("book_name") or "").strip()
            author = (sug.get("author") or "").strip() or AUTHOR_FALLBACK
            desc = (sug.get("description") or "").strip() or "Suggested further reading related to the query."
            if not name:
                continue
            key = _dedupe_key(name, author)
            if key in seen:
                continue
            seen.add(key)

            # Status + book_id come from the DATABASE, not the LLM.
            matched = _match_catalog(db, name, author)
            if matched is not None:
                item = RecommendationItem(
                    book_name=matched.title,
                    author=matched.author or AUTHOR_FALLBACK,
                    description=matched.description or desc,
                    library_status=_status_for_book(matched),
                    book_id=matched.id,
                )
            else:
                item = RecommendationItem(
                    book_name=name,
                    author=author,
                    description=desc,
                    library_status="not_in_library",
                    book_id=None,
                )
            items.append(item)
            if len(items) >= top_k:
                break

    return RecommendationResponse(query=query, recommendations=items[:top_k])


def _llm_suggestions(query: str, n: int, already: list[str]) -> list[dict]:
    llm = get_llm()
    system = (
        "You are a librarian who suggests relevant books. Respond with a JSON "
        "object of the form {\"suggestions\": [{\"book_name\": str, \"author\": "
        "str, \"description\": str}]}. Only include these three fields per book. "
        "Do not invent availability or stock information."
    )
    user = (
        f"Suggest up to {n} real books for the query: '{query}'.\n"
        f"Avoid duplicating these already-listed books: {already or 'none'}."
    )
    data = llm.complete_json(system, user)
    if isinstance(data, dict):
        sugg = data.get("suggestions") or data.get("books") or []
        if isinstance(sugg, list):
            return [s for s in sugg if isinstance(s, dict)]
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    return []


def _match_catalog(db: Session, name: str, author: str):
    """Confident catalog match by normalized title (+author when present)."""
    target_title = _norm(name)
    target_author = _norm(author)
    # small catalogs: linear scan is fine and avoids DB-specific SQL
    books, _ = repo.list_books(db, q=None, page=1, page_size=1000)
    best = None
    for book in books:
        if _norm(book.title) == target_title:
            if not target_author or target_author in _norm(book.author) or _norm(book.author) in target_author:
                return book
            best = best or book
    return best
