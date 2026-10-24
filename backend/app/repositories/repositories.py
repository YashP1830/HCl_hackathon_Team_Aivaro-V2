"""Shared database access (Member A owns these). Services depend on these
interfaces, not on raw ORM queries scattered across the codebase."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Book, BookEmbedding, Faq, Loan, PurchaseEvent, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------- Users ---------
def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, *, name: str, email: str, password_hash: str, role: str = "user") -> User:
    user = User(name=name, email=email.lower(), password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --------- Books ---------
def get_book(db: Session, book_id: str) -> Book | None:
    return db.get(Book, book_id)


def list_books(db: Session, *, q: str | None, page: int, page_size: int) -> tuple[list[Book], int]:
    stmt = select(Book)
    count_stmt = select(func.count(Book.id))
    if q:
        like = f"%{q.lower()}%"
        cond = func.lower(Book.title).like(like) | func.lower(Book.author).like(like) | func.lower(Book.genre).like(like)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Book.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt)), total


def create_book(db: Session, data: dict) -> Book:
    book = Book(**data, embedding_status="pending")
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def update_book(db: Session, book: Book, data: dict) -> Book:
    for k, v in data.items():
        setattr(book, k, v)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def set_embedding(db: Session, *, book_id: str, vector_json: str, text: str, model: str, dim: int) -> None:
    existing = db.get(BookEmbedding, book_id)
    if existing:
        existing.embedding = vector_json
        existing.embedded_text = text
        existing.embedding_model = model
        existing.dimension = dim
    else:
        db.add(BookEmbedding(book_id=book_id, embedding=vector_json, embedded_text=text, embedding_model=model, dimension=dim))
    book = db.get(Book, book_id)
    if book:
        book.embedding_status = "ready"
    db.commit()


def mark_embedding_failed(db: Session, book_id: str) -> None:
    book = db.get(Book, book_id)
    if book:
        book.embedding_status = "failed"
        db.commit()


def all_embeddings(db: Session) -> list[BookEmbedding]:
    return list(db.scalars(select(BookEmbedding)))


# --------- FAQs ---------
def list_faqs(db: Session) -> list[Faq]:
    return list(db.scalars(select(Faq)))


def create_faq(db: Session, *, question: str, answer: str, category: str = "general") -> Faq:
    faq = Faq(question=question, answer=answer, category=category)
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


# --------- Loans ---------
def get_loan(db: Session, loan_id: str) -> Loan | None:
    return db.get(Loan, loan_id)


def list_user_loans(db: Session, user_id: str) -> list[Loan]:
    return list(db.scalars(select(Loan).where(Loan.user_id == user_id).order_by(Loan.due_at)))


def create_loan(db: Session, *, user_id: str, book_id: str, period_days: int) -> Loan:
    now = _now()
    loan = Loan(user_id=user_id, book_id=book_id, borrowed_at=now, due_at=now + timedelta(days=period_days))
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan


def overdue_unreturned_loans(db: Session) -> list[Loan]:
    now = _now()
    stmt = select(Loan).where(Loan.returned_at.is_(None), Loan.due_at < now)
    return list(db.scalars(stmt))


# --------- Purchases ---------
def purchases_between(db: Session, start: datetime, end: datetime) -> list[PurchaseEvent]:
    stmt = select(PurchaseEvent).where(PurchaseEvent.purchased_at >= start, PurchaseEvent.purchased_at <= end)
    return list(db.scalars(stmt))


def count_books(db: Session) -> int:
    return db.scalar(select(func.count(Book.id))) or 0


def count_purchases(db: Session) -> int:
    return db.scalar(select(func.count(PurchaseEvent.id))) or 0
