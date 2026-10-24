"""Canonical ORM models (Member A owns these).

Schema mirrors KNOWLEDGE_TRANSFER.md Section 5. Embeddings are stored as JSON
text so the exact same schema works on SQLite and PostgreSQL. When running on
PostgreSQL with pgvector the vector search can additionally use a native column,
but the JSON copy keeps the app portable and always functional.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)  # user | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    loans: Mapped[list["Loan"]] = relationship(back_populates="user")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String(255), default="")
    publisher: Mapped[str] = mapped_column(String(255), default="")
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|ready|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    embedding: Mapped["BookEmbedding | None"] = relationship(
        back_populates="book", uselist=False, cascade="all, delete-orphan"
    )
    loans: Mapped[list["Loan"]] = relationship(back_populates="book")

    @property
    def availability_status(self) -> str:
        return "available" if self.stock_quantity > 0 else "out_of_stock"


class BookEmbedding(Base):
    __tablename__ = "book_embeddings"

    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    # JSON-encoded list[float]; portable across SQLite/Postgres.
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    embedded_text: Mapped[str] = mapped_column(Text, default="")
    embedding_model: Mapped[str] = mapped_column(String(128), default="")
    dimension: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    book: Mapped["Book"] = relationship(back_populates="embedding")


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id"), index=True)
    borrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Dedupe key for reminders: set when a reminder has been sent for this loan.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="loans")
    book: Mapped["Book"] = relationship(back_populates="loans")


class Faq(Base):
    __tablename__ = "faqs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(128), default="general")
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[float]
    embedding_model: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PurchaseEvent(Base):
    __tablename__ = "purchase_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    book_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    book_title: Mapped[str] = mapped_column(String(512), default="")
    genre: Mapped[str] = mapped_column(String(255), default="")
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (UniqueConstraint("id", name="uq_purchase_id"),)
