"""curl_cffi-based HTTP client adapter — implements IHttpClient."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from curl_cffi import requests as curl_requests
from curl_cffi.requests.errors import RequestsError, CurlError

from src.adapters.http.header_pool import IMPERSONATE_PROFILES, get_headers
from src.core.models.exceptions import HttpClientError
from src.core.models.http_models import HttpResponse
from src.core.ports.http_client import IHttpClient

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Mapping


class CurlCffiClient:
    """HTTP client using curl_cffi for TLS fingerprint impersonation.

    Implements IHttpClient protocol with:
    - Session pool keyed by impersonate profile for connection reuse
    - Realistic header rotation via header_pool
    - All network errors wrapped in HttpClientError
    - HTTP 4xx/5xx returned normally in HttpResponse (not exceptions)
    - Accurate latency measurement

    Args:
        default_impersonate: Default curl_cffi impersonate profile.
    """

    def __init__(self, default_impersonate: str = "chrome124") -> None:
        if default_impersonate not in IMPERSONATE_PROFILES:
            raise ValueError(f"Invalid impersonate profile: {default_impersonate}")

        self._default_impersonate = default_impersonate
        self._sessions: dict[str, curl_requests.AsyncSession] = {}
        self._profile_order = IMPERSONATE_PROFILES.copy()
        self._current_profile_index = 0

        # Metrics counters
        self._total_requests = 0
        self._blocked_count = 0  # 403, 429, CAPTCHA
        self._success_count = 0  # 2xx
        self._error_count = 0    # network errors
        self._latency_sum = 0.0
        self._fingerprint_rotations = 0

    # ── IHttpClient Protocol Implementation ────────────────────────────

    async def fetch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        impersonate: str | None = None,
        timeout: float = 30.0,
    ) -> HttpResponse:
        """Execute HTTP GET with TLS fingerprint impersonation.

        Args:
            url: Target URL (must be https).
            headers: Optional custom headers (merged with session defaults).
            impersonate: curl_cffi impersonate target (e.g., "chrome124").
            timeout: Request timeout in seconds.

        Returns:
            HttpResponse with status_code, body, headers, final_url, latency_ms,
            and tls_fingerprint_used.

        Raises:
            HttpClientError: On network-level failures (DNS, connection, TLS, timeout).
        """
        profile = impersonate or self._default_impersonate
        if profile not in IMPERSONATE_PROFILES:
            profile = self._default_impersonate

        session = await self._get_session(profile)

        # Build headers: defaults from header_pool + caller overrides
        request_headers = get_headers(profile)
        if headers:
            request_headers.update(headers)

        logger.debug(
            "Fetching %s (impersonate=%s, timeout=%.0fs)",
            url,
            profile,
            timeout,
        )
        start_time = time.perf_counter()
        try:
            response = await session.get(
                url,
                headers=request_headers,
                timeout=timeout,
                impersonate=profile,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000.0

        except (RequestsError, CurlError) as e:
            self._error_count += 1
            raise HttpClientError(f"Network error for {url}: {e}") from e

        # Update metrics
        self._total_requests += 1
        self._latency_sum += latency_ms

        if 200 <= response.status_code < 300:
            self._success_count += 1
        elif response.status_code in (403, 429):
            self._blocked_count += 1

        # Normalize response headers to lowercase keys (HTTP/2 spec)
        resp_headers: dict[str, str] = {}
        for k, v in response.headers.items():
            resp_headers[k.lower()] = v

        return HttpResponse(
            status_code=response.status_code,
            body=response.text,
            headers=resp_headers,
            final_url=str(response.url),
            latency_ms=latency_ms,
            tls_fingerprint_used=profile,
        )

    async def rotate_fingerprint(self) -> str:
        """Rotate to the next TLS impersonation profile.

        Returns:
            The new impersonate profile string.
        """
        self._current_profile_index = (self._current_profile_index + 1) % len(self._profile_order)
        new_profile = self._profile_order[self._current_profile_index]
        self._fingerprint_rotations += 1
        return new_profile

    def session_metrics(self) -> dict[str, int]:
        """Return session-level telemetry snapshot.

        Returns:
            Dict with total_requests, blocked_requests, success_requests,
            avg_latency_ms, active_sessions, fingerprint_rotations, errors.
        """
        avg_latency = 0
        if self._total_requests > 0:
            avg_latency = int(self._latency_sum / self._total_requests)

        return {
            "total_requests": self._total_requests,
            "blocked_requests": self._blocked_count,
            "success_requests": self._success_count,
            "avg_latency_ms": avg_latency,
            "active_sessions": len(self._sessions),
            "fingerprint_rotations": self._fingerprint_rotations,
            "errors": self._error_count,
        }

    # ── Internal Helpers ──────────────────────────────────────────────

    async def _get_session(self, profile: str) -> curl_requests.AsyncSession:
        """Get or create an AsyncSession for the given profile."""
        if profile not in self._sessions:
            # Create session with default headers from header_pool
            session = curl_requests.AsyncSession()
            session.headers.update(get_headers(profile))
            self._sessions[profile] = session
        return self._sessions[profile]

    async def close(self) -> None:
        """Close all sessions and clean up resources."""
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()

    async def __aenter__(self) -> CurlCffiClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()