"""Seed demo data so a clean clone shows a working end-to-end journey:
admin + demo user, a catalog (with embeddings), FAQs, loans (incl. an overdue
one), and a purchase log for analytics. Idempotent: safe to run repeatedly.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import build_book_text, get_embeddings
from app.core.config import settings
from app.core.security import hash_password
from app.models.models import Book, BookEmbedding, Faq, Loan, PurchaseEvent, User
from app.repositories import repositories as repo

logger = logging.getLogger("app.db.seed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


SEED_BOOKS = [
    dict(title="Generative AI Fundamentals", author="Ada Lovelace", genre="Artificial Intelligence",
         publisher="TechPress", publication_year=2024, stock_quantity=4,
         description="A clear introduction to generative AI concepts, from language models to diffusion."),
    dict(title="Deep Learning with Python", author="François Chollet", genre="Machine Learning",
         publisher="Manning", publication_year=2021, stock_quantity=2,
         description="Practical deep learning using Keras and TensorFlow, written by the creator of Keras."),
    dict(title="Hands-On Machine Learning", author="Aurélien Géron", genre="Machine Learning",
         publisher="O'Reilly", publication_year=2022, stock_quantity=0,
         description="End-to-end machine learning with Scikit-Learn, Keras and TensorFlow."),
    dict(title="Fluent Python", author="Luciano Ramalho", genre="Programming",
         publisher="O'Reilly", publication_year=2022, stock_quantity=3,
         description="Writing idiomatic, effective Python using its most powerful features."),
    dict(title="Designing Data-Intensive Applications", author="Martin Kleppmann", genre="Data Engineering",
         publisher="O'Reilly", publication_year=2017, stock_quantity=1,
         description="The big ideas behind reliable, scalable and maintainable data systems."),
    dict(title="Natural Language Processing in Action", author="Hobson Lane", genre="Artificial Intelligence",
         publisher="Manning", publication_year=2019, stock_quantity=0,
         description="Understanding and building systems that read, interpret and generate human language."),
    dict(title="The Pragmatic Programmer", author="Andrew Hunt, David Thomas", genre="Software Engineering",
         publisher="Addison-Wesley", publication_year=2019, stock_quantity=5,
         description="Timeless, practical advice on the craft of software development."),
    dict(title="Introduction to Information Retrieval", author="Christopher D. Manning", genre="Information Retrieval",
         publisher="Cambridge", publication_year=2008, stock_quantity=2,
         description="Foundational text on search, indexing and retrieval, including vector space models."),
]

SEED_FAQS = [
    dict(question="How do I borrow a book?",
         answer="Sign in, open the book's page in the catalog, and click Borrow. The book is due back after your library's loan period.",
         category="borrowing"),
    dict(question="How do I return a book?",
         answer="Go to 'My Loans', find the book, and click Return. Returning it frees up stock for other readers.",
         category="borrowing"),
    dict(question="What happens if my book is overdue?",
         answer="You'll receive an email reminder once the due date has passed. Please return overdue books as soon as possible.",
         category="loans"),
    dict(question="How many books can I borrow at once?",
         answer="The default policy allows several active loans at a time; check with the library for the exact limit.",
         category="loans"),
    dict(question="How do I search for books on a topic?",
         answer="Use the Recommendations page and describe what you're looking for. The assistant combines our catalog with extra suggestions.",
         category="search"),
    dict(question="How do I reset my password?",
         answer="Password reset is handled by the library staff for this prototype. Contact support for help.",
         category="account"),
]


def _ensure_admin(db: Session) -> None:
    if not repo.get_user_by_email(db, settings.admin_email):
        repo.create_user(
            db, name=settings.admin_name, email=settings.admin_email,
            password_hash=hash_password(settings.admin_password), role="admin",
        )
        logger.info("Created bootstrap admin %s", settings.admin_email)


def _ensure_demo_user(db: Session) -> User:
    user = repo.get_user_by_email(db, "user@example.com")
    if not user:
        user = repo.create_user(
            db, name="Demo Reader", email="user@example.com",
            password_hash=hash_password("user123"), role="user",
        )
    return user


def _seed_books(db: Session) -> list[Book]:
    existing = db.scalar(select(Book).limit(1))
    if existing:
        return list(db.scalars(select(Book)))
    emb = get_embeddings()
    books: list[Book] = []
    for data in SEED_BOOKS:
        book = Book(**data, embedding_status="pending")
        db.add(book)
        db.flush()  # get id
        try:
            text = build_book_text(title=book.title, author=book.author, description=book.description,
                                   genre=book.genre, publisher=book.publisher)
            vec = emb.embed(text)
            db.add(BookEmbedding(book_id=book.id, embedding=json.dumps(vec), embedded_text=text,
                                 embedding_model=emb.model, dimension=emb.dim))
            book.embedding_status = "ready"
        except Exception:
            logger.exception("Seed embedding failed for %s", book.title)
            book.embedding_status = "failed"
        books.append(book)
    db.commit()
    logger.info("Seeded %s books", len(books))
    return books


def _seed_faqs(db: Session) -> None:
    if db.scalar(select(Faq).limit(1)):
        return
    emb = get_embeddings()
    for data in SEED_FAQS:
        faq = Faq(**data)
        try:
            vec = emb.embed(f"{faq.question}\n{faq.answer}")
            faq.embedding = json.dumps(vec)
            faq.embedding_model = emb.model
        except Exception:
            pass
        db.add(faq)
    db.commit()
    logger.info("Seeded %s FAQs", len(SEED_FAQS))


def _seed_loans(db: Session, user: User, books: list[Book]) -> None:
    if db.scalar(select(Loan).limit(1)):
        return
    now = _now()
    if not books:
        return
    # An overdue, unreturned loan -> exercises the reminder job.
    overdue_book = books[0]
    db.add(Loan(user_id=user.id, book_id=overdue_book.id,
                borrowed_at=now - timedelta(days=21), due_at=now - timedelta(days=7)))
    # A current, not-yet-due loan.
    if len(books) > 1:
        db.add(Loan(user_id=user.id, book_id=books[1].id,
                    borrowed_at=now - timedelta(days=2), due_at=now + timedelta(days=12)))
    # A returned loan -> must NOT get reminders.
    if len(books) > 3:
        db.add(Loan(user_id=user.id, book_id=books[3].id,
                    borrowed_at=now - timedelta(days=30), due_at=now - timedelta(days=16),
                    returned_at=now - timedelta(days=18)))
    db.commit()
    logger.info("Seeded demo loans")


def _seed_purchases(db: Session, books: list[Book]) -> None:
    if db.scalar(select(PurchaseEvent).limit(1)):
        return
    now = _now()
    import random

    rng = random.Random(42)  # deterministic seed data
    for i in range(60):
        book = rng.choice(books)
        days_ago = rng.randint(0, 300)
        qty = rng.randint(1, 3)
        price = rng.choice([399, 499, 599, 699, 899])
        db.add(PurchaseEvent(
            user_id=None, book_id=book.id, book_title=book.title, genre=book.genre,
            purchased_at=now - timedelta(days=days_ago), quantity=qty, amount=float(price * qty),
        ))
    db.commit()
    logger.info("Seeded purchase events")


def seed_all(db: Session) -> None:
    _ensure_admin(db)
    user = _ensure_demo_user(db)
    books = _seed_books(db)
    _seed_faqs(db)
    _seed_loans(db, user, books)
    _seed_purchases(db, books)
