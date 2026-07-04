"""KeywordValidator — promo keyword gatekeeper for parsed candidates."""

from __future__ import annotations

import logging

from src.core.models.parsed_candidate import ParsedCandidate

logger = logging.getLogger(__name__)


class KeywordValidator:
    """Validates ParsedCandidates by checking for known promo keywords in the title.

    Stateless — keyword lists are class-level constants. Performs case-insensitive
    substring matching against Arabic and English promo keywords (خصم, عرض, وفر,
    deal, promo, save, sale, etc.). Used as a binary gatekeeper: candidates whose
    raw_title contains no recognised promo keyword are rejected.

    Per Architecture Blueprint Section 2.3, the parser already assigns a
    confidence_score based on DOM pattern matching. This validator provides
    an orthogonal signal — semantic content filtering — before the candidate
    reaches the dedup engine.

    TEST_MODE (class attribute):
        When True, is_valid() accepts ALL candidates with a non-empty title.
        This bypasses keyword matching for pipeline integration testing.
        Set to False for production operation.
    """

    # ── Test Mode Gate ─────────────────────────────────────────────────
    TEST_MODE: bool = True  # ✅ TEMPORARY: bypass keyword filter for initial testing

    # Arabic promo keywords (localised for Egypt / MENA e-commerce)
    ARABIC_KEYWORDS: tuple[str, ...] = (
        "خصم",
        "عرض",
        "وفر",
        "تخفيضات",
        "صفقة",
        "كوبون",
        "توفير",
    )

    # English promo keywords (common on Amazon Egypt's bilingual promo pages)
    ENGLISH_KEYWORDS: tuple[str, ...] = (
        "deal",
        "promo",
        "save",
        "sale",
        "discount",
        "coupon",
        "offer",
    )

    @classmethod
    def is_valid(cls, candidate: ParsedCandidate) -> bool:
        """Check whether a parsed candidate's title contains a known promo keyword.

        Performs case-insensitive substring matching against both Arabic and
        English keyword sets. Returns True if any keyword is found anywhere
        in the candidate's raw_title.

        When TEST_MODE is True, all candidates with non-empty titles pass —
        useful for pipeline integration testing when Amazon page content may
        not contain the expected promo keywords.

        Args:
            candidate: The ParsedCandidate to validate (frozen dataclass,
                read-only access — never mutated).

        Returns:
            True if the raw_title contains at least one recognised promo keyword;
            False if no keyword match is found (candidate is likely noise).
        """
        # ── TEST_MODE bypass: accept any candidate with a non-empty title ──
        if cls.TEST_MODE:
            return bool(candidate.raw_title and len(candidate.raw_title.strip()) > 1)

        title_lower = candidate.raw_title.lower()

        for keyword in cls.ARABIC_KEYWORDS:
            if keyword in title_lower:
                return True

        for keyword in cls.ENGLISH_KEYWORDS:
            if keyword in title_lower:
                return True

        return False


# ── Module-level warning when TEST_MODE is active ────────────────────
# This fires on `import src.core.validator` — impossible to miss in logs.
if KeywordValidator.TEST_MODE:
    logger.warning(
        "⚠️  KeywordValidator.TEST_MODE is ON — ALL candidates will pass validation "
        "regardless of promo keyword presence. Set TEST_MODE=False for production."
    )