"""ScanResult entity — the outcome of a single polling cycle (immutable)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.models.promotion import Promotion


class ScanOutcome(Enum):
    """Discriminated outcome of one polling cycle for one TargetEndpoint."""

    SUCCESS_NEW_PROMO = auto()     # Found a never-before-seen promotion
    SUCCESS_NO_CHANGE = auto()     # Page loaded fine, no new promos
    BLOCKED_403 = auto()           # Amazon returned 403 Forbidden
    BLOCKED_CAPTCHA = auto()       # CAPTCHA challenge detected in response
    BLOCKED_THROTTLED = auto()     # 429 Too Many Requests or similar
    SKIPPED_COOLDOWN = auto()      # Endpoint skipped due to active circuit-breaker
    ERROR_CONNECTION = auto()      # Network error, DNS failure, TLS handshake failure
    ERROR_TIMEOUT = auto()         # Request exceeded timeout
    ERROR_PARSE = auto()           # Page loaded but parser could not extract structured data
    ERROR_UNKNOWN = auto()         # Unexpected/internal error caught by global error boundary


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Discriminated union: the outcome of one polling cycle for one TargetEndpoint.

    Immutable — a historical record of what happened. Every code path in the
    orchestrator MUST return a ScanResult; exceptions are never allowed to
    propagate beyond the polling boundary.

    Attributes:
        endpoint_id: Which target was polled.
        outcome: What happened (member of ScanOutcome enum).
        timestamp_utc: When the scan completed.
        new_promotions: Newly-discovered promotions (empty unless SUCCESS_NEW_PROMO).
        http_status_code: HTTP status code if an HTTP response was received.
        error_message: Human-readable error description if the outcome is an error variant.
        latency_ms: Round-trip latency if a response was received.
        tls_fingerprint_used: Which TLS profile was used for this request.
    """

    endpoint_id: str
    outcome: ScanOutcome
    timestamp_utc: float
    new_promotions: tuple[Promotion, ...] = ()  # type: ignore[name-defined]
    http_status_code: int | None = None
    error_message: str | None = None
    latency_ms: float | None = None
    tls_fingerprint_used: str | None = None