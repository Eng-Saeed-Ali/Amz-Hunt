"""Promotion entity — a detected Amazon Egypt promotion (immutable)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Promotion:
    """A detected Amazon Egypt promotion.

    Frozen (immutable) — once created, identity is fixed.
    Equality is based on promo_id only.

    Attributes:
        promo_id: Unique identifier parsed from Amazon (e.g., data-promo-id="XYZ-123").
        url: Direct landing page URL.
        title: Extracted promo title (Arabic/English).
        content_fingerprint: SHA256 of extracted promo-relevant DOM subtree (for dedup).
        first_seen_utc: Unix timestamp of first discovery.
        source_endpoint_id: Which TargetEndpoint produced this discovery.

    Note:
        alert_sent state is managed externally via IStorageBackend.mark_alert_sent(),
        not stored within this immutable entity.
    """

    promo_id: str
    url: str
    title: str
    content_fingerprint: str
    first_seen_utc: float
    source_endpoint_id: str

    @staticmethod
    def compute_fingerprint(raw_html_snippet: str) -> str:
        """Compute SHA256 hash of the normalized HTML snippet representing this promo.

        Args:
            raw_html_snippet: Raw HTML or JSON string content of the promo element.

        Returns:
            A 64-character hex-encoded SHA256 digest of the normalized content.
        """
        normalized = raw_html_snippet.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()