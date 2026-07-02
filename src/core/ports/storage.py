"""IStorageBackend Port — contract for persistent state management."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.core.models.exceptions import StorageError
from src.core.models.promotion import Promotion
from src.core.models.scan_result import ScanResult
from src.core.models.target_endpoint import TargetEndpoint


@runtime_checkable
class IStorageBackend(Protocol):
    """Abstract interface for persistent storage of promotions, endpoints, and scan logs.

    Adapters implementing this Protocol MUST:
      - Be async (non-blocking database access).
      - Be safe for concurrent access from multiple asyncio tasks.
      - Raise StorageError on any persistence failure.
      - Run schema migrations on first connection.

    The primary implementation will be SQLite (via aiosqlite), but this Protocol
    allows swapping to any backend (PostgreSQL, file-based) without changing core logic.
    """

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
        ...

    async def mark_alert_sent(self, promo_id: str) -> None:
        """Mark a promotion's alert as delivered (alert_sent = 1).

        Called after INotificationService confirms successful delivery.

        Args:
            promo_id: The promo_id to mark as alerted.

        Raises:
            StorageError: If the database write fails.
        """
        ...

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
        ...

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
        ...

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
        ...

    async def update_last_polled(self, endpoint_id: str, timestamp_utc: float) -> None:
        """Update the last_polled_utc timestamp for an endpoint.

        Called after every poll attempt (success or failure).

        Args:
            endpoint_id: The endpoint to update.
            timestamp_utc: The Unix timestamp of the poll completion.

        Raises:
            StorageError: If the database write fails.
        """
        ...

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
        ...

    async def reset_failures(self, endpoint_id: str) -> None:
        """Reset consecutive_failures to 0 and clear circuit_breaker_until_utc.

        Called on any successful 200 OK response — the endpoint is immediately healthy.

        Args:
            endpoint_id: The endpoint to reset.

        Raises:
            StorageError: If the database write fails.
        """
        ...

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
        ...

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
        ...
