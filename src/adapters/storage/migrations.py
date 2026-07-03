"""SQLite schema migrations — DDL for promotions, target_endpoints, scan_log."""

from __future__ import annotations

import aiosqlite

CURRENT_SCHEMA_VERSION = 1


async def run_migrations(db: aiosqlite.Connection) -> None:
    """Apply all pending schema migrations idempotently.

    Args:
        db: An open aiosqlite connection.
    """
    # Ensure schema_version table exists
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL
        )
        """
    )

    # Get current applied version
    cursor = await db.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    row = await cursor.fetchone()
    applied_version = row[0] if row else 0

    # Apply pending migrations
    if applied_version < 1:
        await _apply_migration_v1(db)
        await db.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (1, ?)",
            (await _now_utc(),),
        )

    await db.commit()


async def _apply_migration_v1(db: aiosqlite.Connection) -> None:
    """Create initial schema: promotions, target_endpoints, scan_log."""

    # ── promotions table ──────────────────────────────────────────────
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promo_id TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            content_fingerprint TEXT NOT NULL UNIQUE,
            first_seen_utc REAL NOT NULL,
            last_seen_utc REAL NOT NULL,
            source_endpoint_id TEXT NOT NULL,
            alert_sent INTEGER NOT NULL DEFAULT 0,
            CHECK (alert_sent IN (0, 1))
        )
        """
    )

    # Indexes for common query patterns
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_promotions_promo_id ON promotions(promo_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_promotions_first_seen ON promotions(first_seen_utc)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_promotions_alert_sent ON promotions(alert_sent)"
    )

    # ── target_endpoints table ────────────────────────────────────────
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS target_endpoints (
            endpoint_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            parser_type TEXT NOT NULL,
            poll_interval_seconds INTEGER NOT NULL,
            active_hours_start INTEGER NOT NULL,
            active_hours_end INTEGER NOT NULL,
            impersonate_profile TEXT NOT NULL,
            priority INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_polled_utc REAL NOT NULL DEFAULT 0.0,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            circuit_breaker_until_utc REAL NOT NULL DEFAULT 0.0,
            CHECK (enabled IN (0, 1)),
            CHECK (priority >= 1 AND priority <= 5)
        )
        """
    )

    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_target_endpoints_enabled ON target_endpoints(enabled)"
    )

    # ── scan_log table (append-only telemetry) ────────────────────────
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            timestamp_utc REAL NOT NULL,
            http_status_code INTEGER,
            latency_ms REAL,
            new_promo_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            tls_fingerprint_used TEXT
        )
        """
    )

    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_log_timestamp ON scan_log(timestamp_utc)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_log_endpoint ON scan_log(endpoint_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_log_outcome ON scan_log(outcome)"
    )


async def _now_utc() -> float:
    """Return current Unix timestamp (UTC)."""
    import time

    return time.time()