"""HttpResponse entity — a captured HTTP response from curl_cffi (immutable)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """A captured HTTP response from curl_cffi.

    Immutable — a snapshot of what the server returned. We store the response
    body as a plain string (HTML or JSON text), which the parser processes.

    Attributes:
        status_code: HTTP status code (200, 403, 429, etc.).
        body: Raw response body text (HTML, JSON, XML).
        headers: Response headers as a dict (keys are lowercased per HTTP/2 spec).
        final_url: The final URL after redirects (may differ from the requested URL).
        latency_ms: Round-trip wall-clock time from request start to body received.
        tls_fingerprint_used: Which impersonate profile was used (e.g., "chrome124").
    """

    status_code: int
    body: str
    headers: dict[str, str]
    final_url: str
    latency_ms: float
    tls_fingerprint_used: str