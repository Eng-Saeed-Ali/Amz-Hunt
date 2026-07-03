"""aiosqlite-backed storage adapter — implements IStorageBackend."""

from __future__ import annotations

import aiosqlite
from typing import TYPE_CHECKING

from src.core.models.exceptions import StorageError
from src.core.models.promotion import Promotion
from src.core.models.scan_result import ScanResult
from src.core.models.target_endpoint import TargetEndpoint
from src.core.ports.storage import IStorageBackend

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class SQLiteBackend:
    """Async SQLite storage backend implementing IStorageBackend protocol.

    Uses aiosqlite for non-blocking database access. All methods are async and
    safe for concurrent access from multiple asyncio tasks. All aiosqlite
    exceptions are wrapped in StorageError.

    Args:
        db_path: Path to the SQLite database file. Defaults to "data/amz_hunt.db".
    """

    def __init__(self, db_path: str = "data/amz_hunt.db") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open database connection and run migrations."""
        if self._db is not None:
            return

        try:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            # Enable WAL mode for better concurrent access
            await self._db.execute("PRAGMA journal_mode=WAL")
            # Run schema migrations
            from src.adapters.storage.migrations import run_migrations

            await run_migrations(self._db)
        except aiosqlite.Error as e:
            raise StorageError(f"Failed to connect to database: {e}") from e

    async def close(self) -> None:
        """Close database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> SQLiteBackend:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # ── Promotion Lifecycle ──────────────────────────────────────────

    async def upsert_promotion(self, promotion: Promotion) -> bool:
        """Insert a new promotion or update last_seen_utc if it already exists.

        Dedup is enforced by UNIQUE constraint on content_fingerprint in the schema.
        If the fingerprint already exists, only last_seen_utc is updated.

        Args:
            promotion: The Promotion to persist.

        Returns:
            True if this was a NEW insertion (first time seeing this fingerprint),
            False if the promotion already existed (updated last_seen_utc only).

        Raises:
            StorageError: If the database write fails.
        """
        self._ensure_connected()
        try:
            # Try to insert new promotion
            cursor = await self._db.execute(
                """
                INSERT INTO promotions (
                    promo_id, url, title, content_fingerprint,
                    first_seen_utc, last_seen_utc, source_endpoint_id, alert_sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    promotion.promo_id,
                    promotion.url,
                    promotion.title,
                    promotion.content_fingerprint,
                    promotion.first_seen_utc,
                    promotion.first_seen_utc,  # last_seen_utc = first_seen_utc on insert
                    promotion.source_endpoint_id,
                ),
            )
            await self._db.commit()

            # rowcount > 0 means INSERT succeeded (new row)
            if cursor.rowcount > 0:
                return True

            # INSERT failed due to UNIQUE constraint on content_fingerprint
            # Update last_seen_utc for the existing row
            await self._db.execute(
                "UPDATE promotions SET last_seen_utc = ? WHERE content_fingerprint = ?",
                (promotion.first_seen_utc, promotion.content_fingerprint),
            )
            await self._db.commit()
            return False

        except aiosqlite.Error as e:
            raise StorageError(f"Failed to upsert promotion: {e}") from e

    async def mark_alert_sent(self, promo_id: str) -> None:
        """Mark a promotion's alert as delivered (alert_sent = 1).

        Called after INotificationService confirms successful delivery.

        Args:
            promo_id: The promo_id to mark as alerted.

        Raises:
            StorageError: If the database write fails.
        """
        self._ensure_connected()
        try:
            await self._db.execute(
                "UPDATE promotions SET alert_sent = 1 WHERE promo_id = ?",
                (promo_id,),
            )
            await self._db.commit()
        except aiosqlite.Error as e:
            raise StorageError(f"Failed to mark alert sent: {e}") from e

    async def was_alert_sent(self, promo_id: str) -> bool:
        """Check whether an alert has already been sent for this promotion.

        Prevents duplicate notifications in case of retry races.

        Args:
            promo_id: The promo_id to check.

        Returns:
            True if alert_sent == 1, False otherwise.

        Raises:
            StorageError: If the database read fails.
        """
        self._ensure_connected()
        try:
            cursor = await self._db.execute(
                "SELECT alert_sent FROM promotions WHERE promo_id = ?",
                (promo_id,),
            )
            row = await cursor.fetchone()
            return bool(row and row[0] == 1)
        except aiosqlite.Error as e:
            raise StorageError(f"Failed to check alert sent status: {e}") from e

    async def get_promotion_by_fingerprint(self, fingerprint: str) -> Promotion | None:
        """Look up a promotion by its content_fingerprint.

        Used by the dedup engine before creating a new Promotion.

        Args:
            fingerprint: SHA256 content fingerprint hex string.

        Returns:
            The existing Promotion if found, None if this fingerprint is new.

        Raises:
            StorageError: If the database read fails.
        """
        self._ensure_connected()
        try:
            cursor = await self._db.execute(
                """
                SELECT promo_id, url, title, content_fingerprint,
                       first_seen_utc, source_endpoint_id
                FROM promotions
                WHERE content_fingerprint = ?
                """,
                (fingerprint,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            return Promotion(
                promo_id=row[0],
                url=row[1],
                title=row[2],
                content_fingerprint=row[3],
                first_seen_utc=row[4],
                source_endpoint_id=row[5],
            )
        except aiosqlite.Error as e:
            raise StorageError(f"Failed to get promotion by fingerprint: {e}") from e

    # ── Target Endpoint Management ────────────────────────────────────

    async def get_active_targets(self) -> list[TargetEndpoint]:
        """Return all enabled TargetEndpoints.

        Used by the orchestrator to build the polling schedule.
        Excludes endpoints where enabled = 0.

        Returns:
            A list of TargetEndpoint dataclass instances with current mutable state
            (last_polled_utc, consecutive_failures, circuit_breaker_until_utc)
            loaded from the database.

        Raises:
            StorageError: If the database read fails.
        """
        self._ensure_connected()
        try:
            cursor = await self._db.execute(
                """
                SELECT endpoint_id, url, parser_type, poll_interval_seconds,
                       active_hours_start, active_hours_end, impersonate_profile,
                       priority, enabled, last_polled_utc, consecutive_failures,
                       circuit_breaker_until_utc
                FROM target_endpoints
                WHERE enabled = 1
                """,
            )
            rows = await cursor.fetchall()

            targets: list[TargetEndpoint] = []
            for row in rows:
                targets.append(
                    TargetEndpoint(
                        endpoint_id=row[0],
                        url=row[1],
                        parser_type=row[2],
                        poll_interval_seconds=row[3],
                        active_hours=(row[4], row[5]),
                        impersonate_profile=row[6],
                        priority=row[7],
                        last_polled_utc=row[9] or 0.0,
                        consecutive_failures=row[10] or 0,
                        circuit_breaker_until_utc=row[11] or 0.0,
                    )
                )
            return targets

        except aiosqlite.Error as e:
            raise StorageError(f"Failed to get active targets: {e}") from e

    async def update_last_polled(self, endpoint_id: str, timestamp_utc: float) -> None:
        """Update the last_polled_utc timestamp for an endpoint.

        Called after every poll attempt (success or failure).

        Args:
            endpoint_id: The endpoint to update.
            timestamp_utc: The Unix timestamp of the poll completion.

        Raises:
            StorageError: If the database write fails.
        """
        self._ensure_connected()
        try:
            await self._db.execute(
                "UPDATE target_endpoints SET last_polled_utc = ? WHERE endpoint_id = ?",
                (timestamp_utc, endpoint_id),
            )
            await self._db.commit()
        except aiosqlite.Error as e:
            raise StorageError(f"Failed to update last polled timestamp: {e}") from e

    async def record_failure(self, endpoint_id: str) -> int:
        """Increment consecutive_failures and return the new count.

        Called when a block (403, CAPTCHA, 429) or connection error is detected.
        The returned count is used to compute cooldown tier.

        Args:
            endpoint_id: The endpoint that failed.

        Returns:
            The new consecutive_failures count after increment.

        Raises:
            StorageError: If the database write fails.
        """
        self._ensure_connected()
        try:
            cursor = await self._db.execute(
                """
                UPDATE target_endpoints
                SET consecutive_failures = consecutive_failures + 1
                WHERE endpoint_id = ?
                RETURNING consecutive_failures
                """,
                (endpoint_id,),
            )
            row = await cursor.fetchone()
            await self._db.commit()

            if row is None:
                raise StorageError(f"Endpoint not found: {endpoint_id}")

            return row[0]

        except aiosqlite.Error as e:
            raise StorageError(f"Failed to record failure: {e}") from e

    async def reset_failures(self, endpoint_id: str) -> None:
        """Reset consecutive_failures to 0 and clear circuit_breaker_until_utc.

        Called on any successful 200 OK response — the endpoint is immediately healthy.

        Args:
            endpoint_id: The endpoint to reset.

        Raises:
            StorageError: If the database write fails.
        """
        self._ensure_connected()
        try:
            await self._db.execute(
                """
                UPDATE target_endpoints
                SET consecutive_failures = 0, circuit_breaker_until_utc = 0
                WHERE endpoint_id = ?
                """,
                (endpoint_id,),
            )
            await self._db.commit()
        except aiosqlite.Error as e:
            raise StorageError(f"Failed to reset failures: {e}") from e

    # ── Scan Log (Append-Only Telemetry) ──────────────────────────────

    async def log_scan(self, result: ScanResult) -> None:
        """Append a ScanResult to the scan_log table.

        This is append-only telemetry — no updates, no deletes. Used for debugging,
        monitoring, and the stats dashboard.

        Args:
            result: The completed ScanResult to persist.

        Raises:
            StorageError: If the database write fails.
        """
        self._ensure_connected()
        try:
            await self._db.execute(
                """
                INSERT INTO scan_log (
                    endpoint_id, outcome, timestamp_utc, http_status_code,
                    latency_ms, new_promo_count, error_message, tls_fingerprint_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.endpoint_id,
                    result.outcome.name,  # Store enum as string name
                    result.timestamp_utc,
                    result.http_status_code,
                    result.latency_ms,
                    len(result.new_promotions),
                    result.error_message,
                    result.tls_fingerprint_used,
                ),
            )
            await self._db.commit()
        except aiosqlite.Error as e:
            raise StorageError(f"Failed to log scan result: {e}") from e

    async def get_recent_scan_stats(self, hours: int = 24) -> dict[str, int]:
        """Return aggregated scan statistics for the recent N hours.

        Used by health-check and supervisor for operational dashboards.

        Args:
            hours: Look-back window in hours (default 24).

        Returns:
            A dict with keys like {"total_scans": 1433, "success_new": 12,
            "success_no_change": 1380, "blocked": 41, "errors": 0}.

        Raises:
            StorageError: If the database read fails.
        """
        self._ensure_connected()
        try:
            import time

            since_ts = time.time() - (hours * 3600)

            cursor = await self._db.execute(
                """
                SELECT
                    COUNT(*) as total_scans,
                    SUM(CASE WHEN outcome = 'SUCCESS_NEW_PROMO' THEN 1 ELSE 0 END) as success_new,
                    SUM(CASE WHEN outcome = 'SUCCESS_NO_CHANGE' THEN 1 ELSE 0 END) as success_no_change,
                    SUM(CASE WHEN outcome IN ('BLOCKED_403', 'BLOCKED_CAPTCHA', 'BLOCKED_THROTTLED') THEN 1 ELSE 0 END) as blocked,
                    SUM(CASE WHEN outcome IN ('ERROR_CONNECTION', 'ERROR_TIMEOUT', 'ERROR_PARSE', 'ERROR_UNKNOWN') THEN 1 ELSE 0 END) as errors,
                    SUM(CASE WHEN outcome = 'SKIPPED_COOLDOWN' THEN 1 ELSE 0 END) as skipped_cooldown
                FROM scan_log
                WHERE timestamp_utc >= ?
                """,
                (since_ts,),
            )
            row = await cursor.fetchone()

            return {
                "total_scans": row[0] or 0,
                "success_new": row[1] or 0,
                "success_no_change": row[2] or 0,
                "blocked": row[3] or 0,
                "errors": row[4] or 0,
                "skipped_cooldown": row[5] or 0,
            }

        except aiosqlite.Error as e:
            raise StorageError(f"Failed to get recent scan stats: {e}") from e

    # ── Internal Helpers ──────────────────────────────────────────────

    def _ensure_connected(self) -> None:
        """Ensure database connection is open."""
        if self._db is None:
            raise StorageError("Database not connected. Call connect() first.")

    @property
    def is_connected(self) -> bool:
        """Check if database connection is open."""
        return self._db is not None