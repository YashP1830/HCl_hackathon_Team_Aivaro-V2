"""Application settings.

Design goal: the app MUST start and run on a fresh machine with no external
services configured. Real providers (OpenAI, SerpAPI, SMTP, PostgreSQL) are
used automatically as soon as their keys/URLs are present in the environment
or the .env file. When a key is missing, a safe local fallback is used so the
demo always works. Nothing is removed permanently -- just fill in .env.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (two parents up from this file: app/core/config.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    # Comma-separated list of allowed CORS origins for the frontend dev server.
    frontend_origin: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Auth ---
    # A default is provided so the app runs out of the box; override in prod.
    jwt_secret: str = "change-me-in-production-please-set-JWT_SECRET"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h

    # Bootstrap admin (created on first startup if it does not exist).
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"
    admin_name: str = "Library Admin"

    # --- Database ---
    # Default: local SQLite file -> zero setup. Set DATABASE_URL to a
    # postgresql+psycopg://... URL to use PostgreSQL (+pgvector) instead.
    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{(DATA_DIR / 'library.db').as_posix()}"
    )

    # --- LLM (OpenAI) ---
    llm_api_key: str = ""          # OPENAI_API_KEY also accepted (see below)
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""          # optional override (Azure/compatible)

    # --- Embeddings ---
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536  # text-embedding-3-small native dim

    # --- Research (SerpAPI) ---
    serpapi_api_key: str = ""
    serpapi_timeout_seconds: int = 20

    # --- Email / SMTP ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "library-no-reply@example.com"
    support_email: str = "support@example.com"

    # --- Loans / reminders ---
    loan_period_days: int = 14
    reminder_cadence: str = "once"  # "once" (on/after due date) or "daily"
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60 * 60  # check hourly; sends once per policy

    # --- External timeouts ---
    openai_timeout_seconds: int = 30

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def resolved_llm_api_key(self) -> str:
        return self.llm_api_key or os.getenv("OPENAI_API_KEY", "")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.resolved_llm_api_key)

    @property
    def embeddings_remote_enabled(self) -> bool:
        return bool(self.resolved_llm_api_key)

    @property
    def serpapi_enabled(self) -> bool:
        return bool(self.serpapi_api_key)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_username)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
