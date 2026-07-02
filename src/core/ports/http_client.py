"""IHttpClient Port — contract for TLS-impersonated HTTP fetching."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.core.models.exceptions import HttpClientError
from src.core.models.http_models import HttpResponse


@runtime_checkable
class IHttpClient(Protocol):
    """Abstract interface for making HTTP requests with TLS fingerprint impersonation.

    Adapters implementing this Protocol MUST:
      - Use curl_cffi for TLS-level browser fingerprint imitation (Chrome/Firefox JA3).
      - Accept session-level header injection (cookies, User-Agent, Client Hints).
      - Report accurate round-trip latency measurements.
      - Raise HttpClientError (NOT generic Exception) on all network-level failures.

    This is the single most critical port — without proper TLS impersonation,
    Amazon's WAF will block us at the TCP handshake before any HTTP headers are sent.
    """

    async def fetch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        impersonate: str | None = None,
        timeout: float = 30.0,
    ) -> HttpResponse:
        """Execute an HTTP GET request with TLS fingerprint impersonation.

        Args:
            url: The full URL to request (scheme must be https).
            headers: Optional HTTP request headers dict. If None, defaults from
                     session-level headers are used.
            impersonate: curl_cffi impersonate target (e.g., "chrome124", "firefox120").
                         If None, use the adapter's default profile.
            timeout: Request timeout in seconds (total, including TLS handshake).

        Returns:
            HttpResponse with status_code, body text, headers, final_url, latency_ms,
            and the tls_fingerprint_used string.

        Raises:
            HttpClientError: On DNS failure, TCP connection refused/reset, TLS handshake
                             failure, socket timeout before any HTTP bytes received,
                             or any other network-level error.
        """
        ...

    async def rotate_fingerprint(self) -> str:
        """Rotate to the next available TLS fingerprint profile.

        Called when a block (403, CAPTCHA, 429) is detected. The adapter maintains
        an ordered list of impersonate profiles and cycles through them.

        Returns:
            The new impersonate profile string (e.g., "chrome120", "firefox120").
        """
        ...

    def session_metrics(self) -> dict[str, int]:
        """Return session-level telemetry for monitoring.

        Must not require async — this is a synchronous snapshot for logging/supervision.

        Returns:
            A dict with keys like {"total_requests": 142, "active_sessions": 3,
            "fingerprint_rotations": 2, "errors": 1}.
        """
        ...