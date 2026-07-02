"""NotificationResult entity — outcome of a single notification attempt (immutable)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NotificationResult:
    """The outcome of attempting to send one notification / alert.

    Immutable — a historical record of whether the notification was delivered.

    Attributes:
        success: True if the message was accepted by the delivery channel.
        channel: The notification channel (e.g., "telegram").
        message_id: Identifier assigned by the delivery service (e.g., Telegram message_id).
        error: Error description if the attempt failed.
        timestamp_utc: When the notification attempt was made.
    """

    success: bool
    channel: str
    message_id: str | None = None
    error: str | None = None
    timestamp_utc: float = 0.0