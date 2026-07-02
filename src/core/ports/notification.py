"""INotificationService Port — contract for delivering alerts to external channels."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.core.models.exceptions import NotificationError
from src.core.models.notification import NotificationResult
from src.core.models.promotion import Promotion


@runtime_checkable
class INotificationService(Protocol):
    """Abstract interface for delivering alerts to notification channels.

    Adapters implementing this Protocol MUST:
      - Be async (non-blocking external API calls).
      - Retry with backoff on transient failures (network errors, API rate limits).
      - Raise NotificationError on permanent failures after retries are exhausted.
      - Return a NotificationResult for every attempt (success or failure).

    The primary implementation will be Telegram Bot API, but this Protocol
    allows adding Discord, WhatsApp, email, or any other channel without
    changing core logic.
    """

    async def send_promo_alert(self, promotion: Promotion) -> NotificationResult:
        """Send a single promotion alert to the configured channel.

        The message MUST include:
          - Promotion title (formatted, not raw)
          - Direct URL to the promo page
          - Discovery timestamp
          - Source endpoint hint

        Args:
            promotion: The newly-discovered Promotion to alert about.

        Returns:
            NotificationResult with success flag, channel name, and message_id (if successful)
            or error description (if failed).

        Raises:
            NotificationError: If all retries are exhausted and delivery is impossible.
                              Should NOT be raised for single transient failures —
                              the adapter handles retries internally.
        """
        ...

    async def send_health_check(self, status: dict[str, int]) -> NotificationResult:
        """Send a system health snapshot to the configured channel.

        Used by the supervisor for periodic "all clear" or "degraded" updates.

        Args:
            status: A dict with scan statistics, e.g.:
                    {"total_scans": 1433, "errors": 0, "active_endpoints": 15}.

        Returns:
            NotificationResult with success/failure details.

        Raises:
            NotificationError: If delivery fails after all retries.
        """
        ...

    async def send_error_alert(
        self, message: str, severity: str = "warning"
    ) -> NotificationResult:
        """Send an operational error/warning alert to the configured channel.

        Used by the orchestrator when persistent failures cross alert thresholds
        (e.g., endpoint blocked 3 times).

        Args:
            message: The alert message text.
            severity: "info", "warning", or "critical" — the adapter should
                      visually differentiate these (e.g., emoji prefix).

        Returns:
            NotificationResult with success/failure details.

        Raises:
            NotificationError: If delivery fails after all retries.
        """
        ...