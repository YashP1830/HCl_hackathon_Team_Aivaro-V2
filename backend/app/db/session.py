"""Database engine/session setup.

Defaults to a local SQLite file for zero-config startup. If DATABASE_URL points
at PostgreSQL the same models are used; pgvector is optional and only engaged
when available (see app.ai.vector_store).
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    connect_args: dict = {}
    if settings.is_sqlite:
        # Needed because the scheduler thread touches the DB too.
        connect_args = {"check_same_thread": False}
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
