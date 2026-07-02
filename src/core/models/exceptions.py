"""Domain Exception Hierarchy — all errors raised by Amz-Hunt inherit from AmzHuntError."""

from __future__ import annotations


class AmzHuntError(Exception):
    """Base exception for all Amz-Hunt errors.

    All domain-specific and adapter-level exceptions inherit from this class.
    This allows the orchestrator's global error boundary to catch and classify
    any error as an ScanResult without needing to know the specific adapter type.
    """

    pass


class HttpClientError(AmzHuntError):
    """Raised by IHttpClient adapters when a network-level failure occurs.

    Examples:
        - DNS resolution failure
        - TCP connection refused/reset
        - TLS handshake failure
        - Socket timeout before any HTTP response bytes received
    """

    pass


class StorageError(AmzHuntError):
    """Raised by IStorageBackend adapters when a persistence operation fails.

    Examples:
        - SQLite database locked
        - Disk full
        - Corrupted database file
        - Schema migration failure
    """

    pass


class NotificationError(AmzHuntError):
    """Raised by INotificationService adapters when a delivery attempt fails.

    Examples:
        - Telegram API returns 4xx/5xx
        - Network failure to Telegram servers
        - Invalid bot token (configuration error)
    """

    pass


class ParserError(AmzHuntError):
    """Raised by IParser adapters when extraction fails due to malformed input.

    Examples:
        - BS4 cannot parse severely malformed HTML
        - JSON endpoint returns non-JSON content
        - Expected CSS selectors produce no matches
    """

    pass


class ValidationError(AmzHuntError):
    """Raised by the validator when a ParsedCandidate fails quality checks.

    Examples:
        - URL is not from an amazon.eg domain
        - Title contains spam/nonsense
        - Content snippet is empty or below minimum length
        - Confidence score below threshold
    """

    pass