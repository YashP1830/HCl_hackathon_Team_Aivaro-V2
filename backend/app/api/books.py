"""Book catalog + admin routes (KT 4.2).

POST /admin/books saves the book then triggers embedding sync and reports the
embedding status. PATCH distinguishes descriptive-field edits (re-embed) from
stock-only updates (no re-embed), per the pgvector sync rule.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.ai.indexing import sync_book_embedding
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.models import User
from app.repositories import repositories as repo
from app.schemas.schemas import (
    AdminBookResponse,
    BookCreate,
    BookListResponse,
    BookOut,
    BookUpdate,
)

router = APIRouter(tags=["books"])

_DESCRIPTIVE_FIELDS = {"title", "author", "description", "genre", "publisher"}


@router.get("/books", response_model=BookListResponse)
def list_books(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    books, total = repo.list_books(db, q=q, page=page, page_size=page_size)
    return BookListResponse(
        items=[BookOut.model_validate(b) for b in books],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: str, db: Session = Depends(get_db)):
    book = repo.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return BookOut.model_validate(book)


@router.post("/admin/books", response_model=AdminBookResponse, status_code=status.HTTP_201_CREATED)
def create_book(body: BookCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    book = repo.create_book(db, body.model_dump())
    emb_status, detail = sync_book_embedding(db, book)
    db.refresh(book)
    return AdminBookResponse(book=BookOut.model_validate(book), embedding_status=emb_status, embedding_detail=detail)


@router.patch("/admin/books/{book_id}", response_model=AdminBookResponse)
def update_book(book_id: str, body: BookUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    book = repo.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")

    descriptive_changed = any(f in changes for f in _DESCRIPTIVE_FIELDS)
    repo.update_book(db, book, changes)

    if descriptive_changed:
        emb_status, detail = sync_book_embedding(db, book)
    else:
        # Stock-only update: do NOT regenerate the embedding.
        emb_status, detail = book.embedding_status, "Stock-only update; embedding not regenerated."

    db.refresh(book)
    return AdminBookResponse(book=BookOut.model_validate(book), embedding_status=emb_status, embedding_detail=detail)


@router.post("/admin/books/{book_id}/reindex", response_model=AdminBookResponse)
def reindex_book(book_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    book = repo.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    emb_status, detail = sync_book_embedding(db, book)
    db.refresh(book)
    return AdminBookResponse(book=BookOut.model_validate(book), embedding_status=emb_status, embedding_detail=detail)
