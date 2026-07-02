"""TargetEndpoint entity — a curated polling target on Amazon Egypt."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TargetEndpoint:
    """A curated polling target — an Amazon Egypt URL or AJAX endpoint known to host promotions.

    NOT frozen because we mutate polling state (last_polled, consecutive_failures,
    circuit_breaker_until_utc). These mutable fields are managed by the orchestrator
    and persisted by IStorageBackend.

    Attributes:
        endpoint_id: UUID or short slug (e.g., "deals-hub-main").
        url: Full URL to poll.
        parser_type: "html_dom" | "json_endpoint".
        poll_interval_seconds: Base interval between polls (jitter applied separately).
        active_hours: (start_hour_utc, end_hour_utc) — e.g., (6, 0) = 06:00 to 00:00 UTC.
        impersonate_profile: TLS fingerprint profile for this endpoint (e.g., "chrome124").
        priority: Lower = higher priority (1=critical, 5=low).
        last_polled_utc: Unix timestamp of last poll attempt.
        consecutive_failures: Count of consecutive failed/blocked polls.
        circuit_breaker_until_utc: If > now_utc, skip this endpoint entirely.
    """

    endpoint_id: str
    url: str
    parser_type: str = "html_dom"
    poll_interval_seconds: int = 60
    active_hours: tuple[int, int] = (6, 0)  # 06:00–00:00 UTC = 08:00–02:00 Cairo
    impersonate_profile: str = "chrome124"
    priority: int = 1

    # Mutable state (managed by orchestrator, persisted by IStorageBackend)
    last_polled_utc: float = 0.0
    consecutive_failures: int = 0
    circuit_breaker_until_utc: float = 0.0

    def is_in_cooldown(self, now_utc: float) -> bool:
        """Return True if the circuit-breaker is active at the given time.

        Args:
            now_utc: Current Unix timestamp.

        Returns:
            True if the endpoint should be skipped because it is in cooldown.
        """
        return now_utc < self.circuit_breaker_until_utc

    def cooldown_remaining_seconds(self, now_utc: float) -> float:
        """Return seconds until cooldown expires (0.0 if not in cooldown).

        Args:
            now_utc: Current Unix timestamp.

        Returns:
            Non-negative float representing remaining cooldown duration.
        """
        return max(0.0, self.circuit_breaker_until_utc - now_utc)