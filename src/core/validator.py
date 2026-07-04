"""KeywordValidator — promo keyword gatekeeper for parsed candidates."""

from __future__ import annotations

from src.core.models.parsed_candidate import ParsedCandidate


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
    """

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

        Args:
            candidate: The ParsedCandidate to validate (frozen dataclass,
                read-only access — never mutated).

        Returns:
            True if the raw_title contains at least one recognised promo keyword;
            False if no keyword match is found (candidate is likely noise).
        """
        title_lower = candidate.raw_title.lower()

        for keyword in cls.ARABIC_KEYWORDS:
            if keyword in title_lower:
                return True

        for keyword in cls.ENGLISH_KEYWORDS:
            if keyword in title_lower:
                return True

        return False