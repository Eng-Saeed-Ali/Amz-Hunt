"""Application configuration loaded from environment variables and .env file.

Uses pydantic-settings for type-safe, validated configuration with sensible
defaults for local development. All sensitive values (tokens, chat IDs) must
be provided via .env — they have no hardcoded defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid impersonate profiles supported by curl_cffi
VALID_IMPERSONATE_PROFILES: frozenset[str] = frozenset({
    "chrome124", "chrome120", "chrome123", "chrome110",
    "chrome99", "chrome100", "chrome101", "chrome107",
    "chrome116", "chrome119", "edge99", "edge101",
    "safari15_5", "safari17_0", "firefox120",
})


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

    # ── Shutdown ──────────────────────────────────────────────────────
    SHUTDOWN_GRACE_PERIOD: float = 10.0
    """Maximum seconds to wait for in-flight tasks to finish on shutdown."""

    @field_validator("DEFAULT_IMPERSONATE_PROFILE")
    @classmethod
    def validate_impersonate(cls, v: str) -> str:
        """Reject unknown curl_cffi impersonate profiles at config-load time."""
        if v not in VALID_IMPERSONATE_PROFILES:
            raise ValueError(
                f"DEFAULT_IMPERSONATE_PROFILE={v!r} is not a valid curl_cffi target. "
                f"Valid options: {sorted(VALID_IMPERSONATE_PROFILES)}"
            )
        return v


# Module-level singleton — import this everywhere
settings = Settings()