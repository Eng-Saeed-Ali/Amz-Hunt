"""Unit tests for Promotion entity — fingerprint determinism and immutability."""

import pytest

from src.core.models.promotion import Promotion


class TestPromotionFingerprintDeterminism:
    """Verify that compute_fingerprint produces stable, deterministic SHA256 output."""

    def test_same_input_produces_same_fingerprint(self) -> None:
        """Identical HTML snippets must yield identical fingerprints."""
        snippet = (
            '<div data-promo-id="XYZ-123" class="deal-card">'
            '<span class="price">EGP 999.00</span>'
            "</div>"
        )
        fp1 = Promotion.compute_fingerprint(snippet)
        fp2 = Promotion.compute_fingerprint(snippet)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA256 hex digest

    def test_different_input_produces_different_fingerprint(self) -> None:
        """Distinct HTML snippets must yield distinct fingerprints."""
        snippet_a = '<div data-promo-id="A-001">Deal A</div>'
        snippet_b = '<div data-promo-id="B-002">Deal B</div>'
        fp_a = Promotion.compute_fingerprint(snippet_a)
        fp_b = Promotion.compute_fingerprint(snippet_b)
        assert fp_a != fp_b

    def test_normalization_case_insensitive(self) -> None:
        """Case differences in input must normalize to the same fingerprint."""
        upper = '<DIV DATA-PROMO-ID="ABC">BIG SALE</DIV>'
        lower = '<div data-promo-id="abc">big sale</div>'
        assert Promotion.compute_fingerprint(upper) == Promotion.compute_fingerprint(
            lower
        )

    def test_normalization_whitespace_insensitive(self) -> None:
        """Surrounding whitespace must be stripped before hashing."""
        padded = "   <div>deal</div>   "
        trimmed = "<div>deal</div>"
        assert Promotion.compute_fingerprint(padded) == Promotion.compute_fingerprint(
            trimmed
        )


class TestPromotionImmutability:
    """Verify that the frozen dataclass cannot be mutated after creation."""

    def test_frozen_dataclass_prevents_assignment(self) -> None:
        """Setting an attribute on a frozen Promotion must raise FrozenInstanceError."""
        promo = Promotion(
            promo_id="TEST-001",
            url="https://example.com/deal",
            title="Test Deal",
            content_fingerprint="a" * 64,
            first_seen_utc=1234567890.0,
            source_endpoint_id="test-ep",
        )
        with pytest.raises(Exception):
            promo.title = "Mutated Title"  # type: ignore[misc]

    def test_equality_is_value_based(self) -> None:
        """Two Promotions with identical fields must be equal."""
        kwargs = {
            "promo_id": "EQ-001",
            "url": "https://example.com/deal",
            "title": "Same Deal",
            "content_fingerprint": "a" * 64,
            "first_seen_utc": 1234567890.0,
            "source_endpoint_id": "test-ep",
        }
        p1 = Promotion(**kwargs)
        p2 = Promotion(**kwargs)
        assert p1 == p2
        assert hash(p1) == hash(p2)