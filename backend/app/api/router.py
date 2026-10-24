"""Central API router wiring (Member A owns this)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import ai_routes, analytics, auth, books, health, loans

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(books.router)
api_router.include_router(ai_routes.router)
api_router.include_router(loans.router)
api_router.include_router(analytics.router)
