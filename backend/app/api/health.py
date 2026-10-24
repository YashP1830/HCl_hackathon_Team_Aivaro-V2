"""Health + runtime status (useful to confirm which providers are active)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "providers": {
            "llm": "openai" if settings.llm_enabled else "local-fallback",
            "embeddings": "openai" if settings.embeddings_remote_enabled else "local-fallback",
            "research": "serpapi" if settings.serpapi_enabled else "disabled-fallback",
            "email": "smtp" if settings.smtp_enabled else "outbox-file",
        },
        "database_kind": "sqlite" if settings.is_sqlite else "external",
        "embedding_model": settings.embedding_model,
        "embedding_dimension": settings.embedding_dimension,
    }
