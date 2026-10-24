"""FastAPI application entrypoint (Member A owns this).

On startup: create tables, seed demo data, start the reminder scheduler. Serves
the pre-built React frontend (if present) so the whole app runs from Python
alone -- no Node required at runtime.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import BACKEND_DIR, settings
from app.db.session import Base, SessionLocal, engine
from app.db.seed import seed_all
from app.jobs.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app.main")

# Frontend build directory: backend/static (copied from frontend/dist at package time)
FRONTEND_DIR = BACKEND_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # import models so tables are registered, then create them
    from app.models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    except Exception:
        logger.exception("Seeding failed (continuing anyway)")
    finally:
        db.close()

    start_scheduler()
    logger.info("Startup complete. LLM=%s Embeddings=%s Research=%s Email=%s",
                "openai" if settings.llm_enabled else "local",
                "openai" if settings.embeddings_remote_enabled else "local",
                "serpapi" if settings.serpapi_enabled else "fallback",
                "smtp" if settings.smtp_enabled else "outbox")
    yield
    stop_scheduler()


app = FastAPI(title="AI-Powered Library & Research Assistant", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Consistent error envelope (KT 4.5) ----
def _error_payload(code: str, message: str, request: Request) -> dict:
    return {"error": {"code": code, "message": message}, "request_id": getattr(request.state, "request_id", None)}


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


_STATUS_CODES = {
    400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN",
    404: "NOT_FOUND", 409: "CONFLICT", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED",
}


@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException):
    code = _STATUS_CODES.get(exc.status_code, "ERROR")
    return JSONResponse(status_code=exc.status_code, content=_error_payload(code, str(exc.detail), request))


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=_error_payload("VALIDATION_ERROR", "The request is invalid.", request))


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content=_error_payload("INTERNAL_ERROR", "An unexpected error occurred.", request))


# ---- API ----
app.include_router(api_router, prefix=settings.api_prefix)


# ---- Serve pre-built frontend (SPA) if present ----
if FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def spa_root():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Let API 404s behave normally; everything else serves the SPA shell.
        candidate = FRONTEND_DIR / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    @app.get("/")
    async def no_frontend():
        return {
            "message": "Backend is running. Frontend build not found.",
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }
