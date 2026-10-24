
"""Application settings.

Primary AI provider: Google Gemini for LLM generation and embeddings.
External search: SerpAPI for research and web-based recommendations.

The app can run without external AI services using local fallbacks.
Database, authentication, email, and scheduler configuration are preserved.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

# backend/ directory (two parents up from app/core/config.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# Application settings
# -------------------------------------------------------------------

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

    # Comma-separated frontend origins.
    frontend_origin: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    # --- Authentication ---
    jwt_secret: str = (
        "change-me-in-production-please-set-JWT_SECRET"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Bootstrap admin account.
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"
    admin_name: str = "Library Admin"

    # --- Database ---
    # Defaults to local SQLite when DATABASE_URL is not configured.
    database_url: str = Field(
        default_factory=lambda: (
            f"sqlite:///{(DATA_DIR / 'library.db').as_posix()}"
        )
    )

    # --- Google Gemini LLM ---
    # Loaded from GEMINI_API_KEY in backend/.env.
    gemini_api_key: str = ""

    # Stable Gemini model identifier.
    llm_model: str = "gemini-3.8-flash"

    # --- Google Gemini embeddings ---
    # Stored book and FAQ vectors must be regenerated when changing models.
    embedding_model: str = "gemini-embedding-001"

    # Supported output dimension for gemini-embedding-001.
    embedding_dimension: int = 1536

    # --- Research and external recommendations (SerpAPI) ---
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

    # --- Loans and reminders ---
    loan_period_days: int = 14

    # "once" or "daily"
    reminder_cadence: str = "once"

    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60 * 60

    # ----------------------------------------------------------------
    # Derived properties
    # ----------------------------------------------------------------

    @property
    def cors_origins(self) -> list[str]:
        """Return normalized CORS origins."""

        return [
            origin.strip()
            for origin in self.frontend_origin.split(",")
            if origin.strip()
        ]

    @property
    def resolved_gemini_api_key(self) -> str:
        """Resolve the Gemini API key from settings or environment."""

        return (
            self.gemini_api_key
            or os.getenv("GEMINI_API_KEY", "")
        )

    @property
    def llm_enabled(self) -> bool:
        """Whether Gemini text generation can be initialized."""

        return bool(self.resolved_gemini_api_key)

    @property
    def embeddings_remote_enabled(self) -> bool:
        """Whether Gemini embeddings can be initialized."""

        return bool(self.resolved_gemini_api_key)

    @property
    def serpapi_enabled(self) -> bool:
        """Whether external SerpAPI search is configured."""

        return bool(self.serpapi_api_key)

    @property
    def smtp_enabled(self) -> bool:
        """Whether SMTP sending is configured."""

        return bool(self.smtp_host and self.smtp_username)

    @property
    def is_sqlite(self) -> bool:
        """Whether the application uses SQLite."""

        return self.database_url.startswith("sqlite")


# -------------------------------------------------------------------
# Cached settings instance
# -------------------------------------------------------------------

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
