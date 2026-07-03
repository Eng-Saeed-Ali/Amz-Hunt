"""HTML DOM parser adapter (BeautifulSoup4 + lxml) — implements IParser."""

from __future__ import annotations

import hashlib
import urllib.parse
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from bs4 import FeatureNotFound as BS4FeatureNotFound

from src.core.models.exceptions import ParserError
from src.core.models.http_models import HttpResponse
from src.core.models.parsed_candidate import ParsedCandidate
from src.core.ports.parser import IParser

if TYPE_CHECKING:
    from bs4.element import Tag


class HTMLDOMParser:
    """HTML DOM parser for Amazon Egypt promotional pages.

    Uses BeautifulSoup4 with lxml backend for fast, tolerant parsing.
    Extracts promotion candidates via CSS selector patterns matching
    Amazon's known promo DOM structures.

    Implements IParser protocol with parser_type = "html_dom".
    """

    # CSS selector patterns ordered by specificity (highest confidence first)
    # Each tuple: (selector, base_confidence, description)
    SELECTOR_PATTERNS: list[tuple[str, float, str]] = [
        # Amazon's internal promo tracking attribute — highest confidence
        ('[data-promo-id]', 1.0, "data-promo-id attribute"),
        # Deal/promo badge class patterns
        ('[class*="dealBadge"]', 0.85, "dealBadge class"),
        ('[class*="promoLabel"]', 0.85, "promoLabel class"),
        ('[class*="couponBadge"]', 0.85, "couponBadge class"),
        ('[class*="DealBadge"]', 0.85, "DealBadge class (PascalCase)"),
        ('[class*="PromoLabel"]', 0.85, "PromoLabel class (PascalCase)"),
        # ID-based patterns
        ('[id*="deal"]', 0.75, "deal in ID"),
        ('[id*="promo"]', 0.75, "promo in ID"),
        ('[id*="Deal"]', 0.75, "Deal in ID"),
        ('[id*="Promo"]', 0.75, "Promo in ID"),
        # Data attribute patterns
        ('[data-deal-id]', 0.8, "data-deal-id attribute"),
        ('[data-promo-id]', 0.8, "data-promo-id attribute"),
        ('[data-asin][data-deal-type]', 0.7, "ASIN with deal type"),
        # Widget/container patterns
        ('[class*="dealContainer"]', 0.65, "dealContainer class"),
        ('[class*="promoContainer"]', 0.65, "promoContainer class"),
        ('[class*="DealCard"]', 0.65, "DealCard class"),
        ('[class*="PromoCard"]', 0.65, "PromoCard class"),
        # Generic card patterns (lower confidence)
        ('[class*="deal"]', 0.55, "deal in class"),
        ('[class*="promo"]', 0.55, "promo in class"),
        ('[class*="offer"]', 0.5, "offer in class"),
        ('[class*="discount"]', 0.5, "discount in class"),
        # Semantic container fallbacks
        ('article[data-promo-id]', 0.9, "article with promo-id"),
        ('li[data-promo-id]', 0.9, "li with promo-id"),
        ('div[data-promo-id]', 0.85, "div with promo-id"),
    ]

    # Title selector patterns within a container
    TITLE_SELECTORS: list[str] = [
        '[class*="title"]',
        '[class*="Title"]',
        '[class*="name"]',
        '[class*="Name"]',
        'h1, h2, h3, h4, h5, h6',
        'a[class*="link"]',
        'span[class*="text"]',
        '.a-text-normal',
        '.a-text-bold',
    ]

    # Link selector patterns within a container
    LINK_SELECTORS: list[str] = [
        'a[href]',
        '[data-url]',
        '[data-link]',
    ]

    @property
    def parser_type(self) -> str:
        """Return the parser type identifier."""
        return "html_dom"

    async def extract_candidates(self, response: HttpResponse) -> list[ParsedCandidate]:
        """Extract promotion candidates from HTML response.

        Args:
            response: HttpResponse with HTML body (status_code assumed 200).

        Returns:
            List of ParsedCandidate objects. Empty list if no matches found.

        Raises:
            ParserError: If HTML is structurally unparseable by BeautifulSoup.
        """
        if not response.body or not response.body.strip():
            return []

        try:
            soup = BeautifulSoup(response.body, "lxml")
        except BS4FeatureNotFound as e:
            raise ParserError("lxml parser not available for BeautifulSoup") from e
        except Exception as e:
            raise ParserError(f"Failed to parse HTML: {e}") from e

        candidates: list[ParsedCandidate] = []
        seen_fingerprints: set[str] = set()

        # Iterate through selector patterns in order of confidence
        for selector, base_confidence, description in self.SELECTOR_PATTERNS:
            try:
                elements = soup.select(selector)
            except Exception:
                # Selector syntax error or other issue — skip this pattern
                continue

            for element in elements:
                candidate = self._extract_from_element(
                    element=element,
                    response=response,
                    base_confidence=base_confidence,
                    selector_desc=description,
                )
                if candidate:
                    # Dedup by content fingerprint within this parse
                    fp = candidate.content_fingerprint
                    if fp not in seen_fingerprints:
                        seen_fingerprints.add(fp)
                        candidates.append(candidate)

        return candidates

    def _extract_from_element(
        self,
        element: "Tag",
        response: HttpResponse,
        base_confidence: float,
        selector_desc: str,
    ) -> ParsedCandidate | None:
        """Extract a ParsedCandidate from a matched DOM element.

        Walks up to find a semantic container, extracts title, URL, and snippet.

        Args:
            element: The matched BeautifulSoup element.
            response: The original HttpResponse for URL resolution.
            base_confidence: Base confidence from the selector that matched.
            selector_desc: Description of the selector for debugging.

        Returns:
            ParsedCandidate if extraction successful, None otherwise.
        """
        # Walk up to find a semantic container (div, li, article, a, section)
        container = element
        for _ in range(5):  # Max 5 levels up
            if container.name in ("div", "li", "article", "a", "section", "aside"):
                break
            if container.parent is None:
                break
            container = container.parent

        # Extract candidate_id
        candidate_id = self._extract_candidate_id(container, element)
        if not candidate_id:
            return None

        # Extract URL
        url = self._extract_url(container, response.final_url)
        if not url:
            url = response.final_url  # Fallback to page URL

        # Extract title
        title = self._extract_title(container)
        if not title:
            return None

        # Content snippet for fingerprinting (container's outer HTML)
        content_snippet = container.prettify()

        # Compute confidence score
        confidence = self._calculate_confidence(container, base_confidence)

        # Use response.final_url as source_endpoint_id (per architecture decision)
        source_endpoint_id = response.final_url

        return ParsedCandidate(
            candidate_id=candidate_id,
            url=url,
            raw_title=title,
            content_snippet=content_snippet,
            parser_name=self.parser_type,
            confidence_score=confidence,
            source_endpoint_id=source_endpoint_id,
        )

    def _extract_candidate_id(self, container: "Tag", matched_element: "Tag") -> str | None:
        """Extract a unique candidate ID from the container or matched element."""
        # Priority 1: data-promo-id (Amazon's canonical ID)
        for attr in ("data-promo-id", "data-deal-id", "data-asin"):
            val = container.get(attr) or matched_element.get(attr)
            if val:
                return str(val).strip()

        # Priority 2: ID attribute
        if container.get("id"):
            return f"id:{container['id']}"

        # Priority 3: href-based ID
        link = container.find("a", href=True)
        if link and link.get("href"):
            href = link["href"]
            # Hash the URL for a stable ID
            return f"url:{hashlib.md5(href.encode()).hexdigest()[:12]}"

        # Priority 4: Hash of container HTML (last resort)
        html = container.prettify()[:500]
        return f"html:{hashlib.md5(html.encode()).hexdigest()[:12]}"

    def _extract_url(self, container: "Tag", base_url: str) -> str | None:
        """Extract and resolve URL from container."""
        # Try data attributes first
        for attr in ("data-url", "data-link", "data-href"):
            val = container.get(attr)
            if val:
                return urllib.parse.urljoin(base_url, str(val).strip())

        # Try link elements
        for selector in self.LINK_SELECTORS:
            link = container.select_one(selector)
            if link and link.get("href"):
                return urllib.parse.urljoin(base_url, link["href"].strip())

        return None

    def _extract_title(self, container: "Tag") -> str | None:
        """Extract title text from container."""
        for selector in self.TITLE_SELECTORS:
            title_elem = container.select_one(selector)
            if title_elem:
                text = title_elem.get_text(strip=True)
                if text and len(text) > 2:  # Filter out noise
                    return text

        # Fallback: container's own text (first 200 chars)
        text = container.get_text(strip=True)
        if text:
            return text[:200]

        return None

    def _calculate_confidence(self, container: "Tag", base_confidence: float) -> float:
        """Calculate final confidence score based on container quality signals."""
        confidence = base_confidence

        # Boost for Amazon-specific attributes
        if container.get("data-promo-id") or container.get("data-deal-id"):
            confidence = min(1.0, confidence + 0.1)
        if container.get("data-asin"):
            confidence = min(1.0, confidence + 0.05)

        # Boost for title presence
        if self._extract_title(container):
            confidence = min(1.0, confidence + 0.05)

        # Boost for link presence
        if self._extract_url(container, ""):
            confidence = min(1.0, confidence + 0.05)

        # Penalty for very large containers (likely page sections, not individual promos)
        text_len = len(container.get_text(strip=True))
        if text_len > 5000:
            confidence *= 0.7
        elif text_len > 2000:
            confidence *= 0.85

        return round(confidence, 2)