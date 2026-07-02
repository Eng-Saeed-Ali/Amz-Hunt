"""ParsedCandidate entity — raw extraction from a parser, before validation/dedup (immutable)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedCandidate:
    """A raw candidate promotion extracted from a page by a parser.

    Immutable — parsers produce these; the validator and dedup engine refine them
    into final Promotion entities.

    Attributes:
        candidate_id: A unique ID derived from the source element (e.g., attr + url hash).
        url: Extracted URL (may be relative; resolved to absolute by the validator).
        raw_title: Raw text extracted from the DOM (may contain noise).
        content_snippet: The raw HTML or JSON content of the promo element (for fingerprinting).
        parser_name: Which parser produced this candidate (e.g., "html_dom").
        confidence_score: 0.0–1.0 heuristic score assigned by the parser (1.0 = certain).
        source_endpoint_id: Which TargetEndpoint's page produced this candidate.
    """

    candidate_id: str
    url: str
    raw_title: str
    content_snippet: str
    parser_name: str
    confidence_score: float
    source_endpoint_id: str