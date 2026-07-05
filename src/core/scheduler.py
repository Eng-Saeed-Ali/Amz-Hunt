"""ActiveHoursScheduler — time-of-day gating for endpoint polling."""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.models.target_endpoint import TargetEndpoint


class ActiveHoursScheduler:
    """Determines whether a TargetEndpoint should be polled based on UTC time windows.

    Stateless — purely evaluates the current UTC hour against an endpoint's
    configured active_hours tuple. Does not perform target selection or jitter
    calculation (those belong in ScanOrchestrator).

    Active hours logic per Architecture Blueprint Section 3.1:
      - Normal range (start <= end): current hour must fall within [start, end].
      - Midnight-wrapping range (start > end): current hour >= start OR <= end.
      - 24/7 mode (start == end, or None values): always active.
    """

    @staticmethod
    def _get_utc_now() -> datetime:
        """Return the current UTC datetime.

        Isolated in its own static method so that unit tests can
        monkey-patch clock behaviour without touching system time.
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def is_active_now(endpoint: TargetEndpoint) -> bool:
        """Check whether the given endpoint is within its active hours right now.

        Evaluates the current UTC hour against endpoint.active_hours.
        Supports three modes:
          1. Normal: start <= end (e.g., (6, 0) → 06:00–00:00 UTC).
          2. Midnight-wrapping: start > end (e.g., (22, 6) → 22:00–06:00).
          3. 24/7: start == end or either value is None.

        Args:
            endpoint: The TargetEndpoint to evaluate. Only reads active_hours;
                does not mutate any fields.

        Returns:
            True if the current UTC hour falls within the endpoint's active
            window, or the endpoint runs 24/7. False if the endpoint is outside
            its scheduled active window and should be skipped.
        """
        start, end = endpoint.active_hours

        # 24/7 mode: identical start/end indicates round-the-clock operation
        # (no meaningful time window), as do None sentinel values.
        if start is None or end is None or start == end:
            return True

        now_utc = ActiveHoursScheduler._get_utc_now()
        current_hour = now_utc.hour

        if start <= end:
            # Normal range: e.g., (6, 18) → 06:00 to 18:00 UTC
            return start <= current_hour <= end
        else:
            # Midnight-wrapping range: e.g., (22, 6) → 22:00 to 06:00 UTC
            return current_hour >= start or current_hour <= end