"""Application configuration loaded from environment variables and .env file.

Uses pydantic-settings for type-safe, validated configuration with sensible
defaults for local development. All sensitive values (tokens, chat IDs) must
be provided via .env — they have no hardcoded defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe application settings loaded from .env and environment.

    All fields can be overridden via environment variables (uppercase) or a
    .env file in the project root. Sensitive fields (TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID) default to empty strings so the application fails
    gracefully if .env is missing.

    Usage:
        from src.config.settings import settings
        db_path = settings.DB_PATH
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars — don't crash
    )

    # ── Telegram Notification ─────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # ── Storage ───────────────────────────────────────────────────────
    DB_PATH: str = "data/amz_hunt.db"

    # ── Logging ───────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── HTTP Client ───────────────────────────────────────────────────
    DEFAULT_IMPERSONATE_PROFILE: str = "chrome124"


# Module-level singleton — import this everywhere
settings = Settings()