"""HTML DOM parser adapter (BeautifulSoup4 + lxml) — implements IParser.

**Hybrid parser:** Amazon Egypt now embeds the full deals payload as JSON
inside a ``<script>`` tag (``assets.mountWidget('slot-14', ...)``) rather
than rendering deal cards in the DOM.  Phase 0 extracts this embedded JSON
before falling back to CSS-selector DOM parsing.

Targets the current Amazon Egypt deals-page DOM (ProductCard-module__ CSS
module classes, data-testid="price-section" anchor). Uses CSS substring
matching against the stable structural anchors; does NOT hardcode the
auto-generated CSS module suffixes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
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

logger = logging.getLogger(__name__)

# Regex to strip price label prefixes (e.g. "With Deal:", "List Price:")
_PRICE_LABEL_RE = re.compile(
    r"^(?:With\s*Deal|Deal\s*Price|List\s*Price|Was|Original)\s*:\s*",
    re.IGNORECASE,
)


class HTMLDOMParser:
    """HTML DOM parser for Amazon Egypt promotional pages.

    **Hybrid strategy** (Phase 0 → Phase 1):

    1. **Embedded JSON** — Amazon Egypt injects the deals payload as a
       ``productSearchResponse`` JSON object inside a ``<script>`` tag.
       If found, products are mapped directly to ParsedCandidate objects
       with perfect fidelity (ASIN, title, link, prices).
    2. **DOM fallback** — If JSON extraction fails (e.g. Amazon changes
       the script format), the existing BeautifulSoup CSS-selector
       pipeline runs against the rendered DOM.

    Uses BeautifulSoup4 with lxml backend. Target-anchored on the stable
    ``data-testid="price-section"`` element that every deal card carries,
    walking upward to the ProductCard-module__ wrapper. CSS selectors use
    substring matching (``[class*="..."]``) so that auto-generated CSS
    module suffixes never break extraction.
    """

    # ── Embedded-JSON markers ──────────────────────────────────────────
    # Only the start marker is needed — the closing brace is located via
    # balanced-brace counting (character-by-character scan), which is
    # immune to minification, key reordering, and trailing commas.
    _JSON_START_MARKER: str = '"productSearchResponse":'

    # ── Selector Patterns ──────────────────────────────────────────────
    # Ordered by specificity / confidence (highest first).  Patterns use
    # substring matching against the Amazon React CSS-module base class
    # names — the dynamic suffixes are ignored.
    SELECTOR_PATTERNS: list[tuple[str, float, str]] = [
        # 1.  Stable anchor: every deal card carries a price section with
        #     this data-testid.  Walk UP from here to the enclosing card.
        ('[data-testid="price-section"]', 1.0, "price-section data-testid"),
        # 2.  ProductCard title wrapper — strong signal.
        ('[class*="ProductCard-module__title_"]', 0.95, "ProductCard title module"),
        # 3.  ProductCard price container — also a strong signal.
        ('[class*="ProductCard-module__priceContainer_"]', 0.90, "ProductCard price container"),
        # 4.  Generic ProductCard-module fallback (catch-all for any card element).
        ('[class*="ProductCard-module__"]', 0.80, "ProductCard module (generic)"),
        # 5.  Badge-based: discount percentage badge (e.g. "13% off").
        ('[data-component="dui-badge"]', 0.75, "dui-badge discount badge"),
        # 6.  Legacy / fallback patterns (kept for compatibility).
        ('[data-promo-id]', 0.70, "data-promo-id (legacy)"),
        ('[data-deal-id]', 0.70, "data-deal-id (legacy)"),
        ('[class*="dealBadge"]', 0.65, "dealBadge (legacy)"),
        ('[class*="DealCard"]', 0.60, "DealCard (legacy)"),
    ]

    # ── Title selectors (tried in order within the container) ──────────
    TITLE_SELECTORS: list[str] = [
        "img[alt]",                                 # product image alt text
        '[class*="ProductCard-module__title_"]',     # title span wrapper
        '[class*="product-title"]',                  # legacy
        '[class*="title"]',                          # generic
        'h1, h2, h3, h4, h5, h6',                   # heading fallback
        '.a-text-normal',
    ]

    # ── Link selectors (tried in order within the container) ───────────
    LINK_SELECTORS: list[str] = [
        'a[href*="/dp/"]',          # ASIN product link — gold standard
        'a[href][class*="ProductCard"]',
        'a[href]',
        '[data-url]',
        '[data-link]',
    ]

    # ── IParser Protocol ──────────────────────────────────────────────

    @property
    def parser_type(self) -> str:
        return "html_dom"

    # ── Phase 0: Embedded-JSON extraction ─────────────────────────────

    @classmethod
    def _extract_from_embedded_json(
        cls, html_text: str, source_url: str
    ) -> list[ParsedCandidate]:
        """Attempt to extract products from the embedded ``productSearchResponse`` JSON.

        Amazon Egypt's current deals page injects the full product list as a
        JSON object inside a ``<script>`` tag:

        .. code-block:: text

            assets.mountWidget('slot-14', { ... "productSearchResponse": {...} ... })

        This method locates the ``productSearchResponse`` object by string-slicing
        between the stable landmark strings, then calls ``json.loads`` to parse it.

        Args:
            html_text: Raw HTML body string.
            source_url: The page URL (used as ``source_endpoint_id``).

        Returns:
            List of ParsedCandidate objects (empty list if extraction fails).
        """
        candidates: list[ParsedCandidate] = []

        # ── Locate the JSON payload ───────────────────────────────
        start_idx = html_text.find(cls._JSON_START_MARKER)
        if start_idx == -1:
            logger.info("Phase 0: embedded JSON start marker not found — skipping Phase 0")
            return candidates

        # Move past the marker to the opening brace
        brace_start = html_text.find("{", start_idx + len(cls._JSON_START_MARKER))
        if brace_start == -1:
            logger.info("Phase 0: no opening brace after productSearchResponse marker")
            return candidates

        # ── Brace-counting scan to find the matching closing brace ──
        # Walk character-by-character from brace_start, tracking brace
        # depth and skipping string literals so braces inside titles /
        # URLs don't throw off the count.  Stops when depth returns
        # to 0 — that's the end of the productSearchResponse object.
        brace_count = 0
        in_string = False
        escape_next = False
        end_idx = None

        for i in range(brace_start, len(html_text)):
            ch = html_text[i]

            if escape_next:
                escape_next = False
                continue

            if in_string:
                if ch == "\\":
                    escape_next = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        if end_idx is None:
            logger.info("Phase 0: could not find matching closing brace — skipping Phase 0")
            return candidates

        json_candidate = html_text[brace_start : end_idx + 1].strip()

        # ── Parse JSON ────────────────────────────────────────────
        try:
            data = json.loads(json_candidate)
        except json.JSONDecodeError as e:
            logger.warning("Phase 0: failed to parse embedded JSON — %s", e)
            return candidates

        products = data.get("products")
        if not isinstance(products, list) or not products:
            logger.info("Phase 0: no 'products' array in embedded JSON")
            return candidates

        # ── Map products to ParsedCandidate ────────────────────────
        seen_asins: set[str] = set()
        for product in products:
            asin = product.get("asin")
            if not asin:
                continue
            if asin in seen_asins:
                continue
            seen_asins.add(asin)

            title = product.get("title", "").strip()
            if not title:
                continue

            link = product.get("link", "")
            url = f"https://www.amazon.eg{link}" if link else source_url

            # Prices: priceToPay = deal price, basisPrice = list price
            price_block = product.get("price", {})
            price_to_pay = price_block.get("priceToPay", {})
            basis_price = price_block.get("basisPrice", {})

            deal_price_raw = price_to_pay.get("price", "")
            list_price_raw = basis_price.get("price", "")

            deal_price = f"EGP {deal_price_raw}" if deal_price_raw else None
            list_price = f"EGP {list_price_raw}" if list_price_raw else None

            # Content snippet: full JSON of this product (prices, ASIN, etc.)
            content_snippet = json.dumps(product, ensure_ascii=False, sort_keys=True)

            candidates.append(
                ParsedCandidate(
                    candidate_id=asin,
                    url=url,
                    raw_title=title,  # Clean product name — no price appended
                    content_snippet=content_snippet,
                    parser_name="html_dom",
                    confidence_score=0.99,  # JSON is canonical — near-perfect confidence
                    source_endpoint_id=source_url,
                    deal_price=deal_price,
                    list_price=list_price,
                )
            )

        logger.info(
            "Embedded JSON: extracted %d product(s) from productSearchResponse",
            len(candidates),
        )
        return candidates

    async def extract_candidates(self, response: HttpResponse) -> list[ParsedCandidate]:
        """Extract promotion candidates from an Amazon Egypt HTML response.

        **Phase 0** — Try embedded JSON first (Amazon Egypt's current format):
        extract ``productSearchResponse`` from ``<script>`` tag, map products
        directly.  If 1+ candidates are found, return immediately.

        **Phase 1** — DOM fallback: BeautifulSoup CSS-selector pipeline against
        rendered card markup.  Runs only if Phase 0 produced zero candidates.
        """
        if not response.body or not response.body.strip():
            return []

        # ── Phase 0: Embedded JSON ────────────────────────────────────
        json_candidates = self._extract_from_embedded_json(
            response.body, response.final_url
        )
        if json_candidates:
            return json_candidates

        logger.info("Phase 0 produced no candidates — falling back to DOM parsing")

        # ── Phase 1: DOM fallback ──────────────────────────────────────
        try:
            soup = BeautifulSoup(response.body, "lxml")
        except BS4FeatureNotFound as e:
            raise ParserError("lxml parser not available for BeautifulSoup") from e
        except Exception as e:
            raise ParserError(f"Failed to parse HTML: {e}") from e

        candidates: list[ParsedCandidate] = []
        seen_fingerprints: set[str] = set()

        for selector, base_confidence, description in self.SELECTOR_PATTERNS:
            try:
                elements = soup.select(selector)
            except Exception:
                continue

            for element in elements:
                candidate = self._extract_from_element(
                    element=element,
                    response=response,
                    base_confidence=base_confidence,
                    selector_desc=description,
                )
                if candidate is None:
                    continue

                fp = hashlib.sha256(
                    candidate.content_snippet.strip().lower().encode("utf-8")
                ).hexdigest()
                if fp not in seen_fingerprints:
                    seen_fingerprints.add(fp)
                    candidates.append(candidate)

        return candidates

    # ── Extraction helpers ────────────────────────────────────────────

    def _extract_from_element(
        self,
        element: Tag,
        response: HttpResponse,
        base_confidence: float,
        selector_desc: str,
    ) -> ParsedCandidate | None:
        """Build a ParsedCandidate from a matched DOM element.

        1. Walk **up** to locate the ProductCard-module__ wrapper.
        2. Extract title (image alt, title span, heading).
        3. Extract URL (ASIN /dp/ link preferred).
        4. Extract deal price + list price from ``.a-offscreen`` spans.
        5. Build ``raw_title`` as ``"[DEAL] Product — EGP X (was Y)"``.
        6. Compute content fingerprint.
        """
        # ── Container: walk up to ProductCard wrapper ─────────────────
        container = self._resolve_card_container(element)
        if container is None:
            return None

        # ── Candidate ID ──────────────────────────────────────────────
        candidate_id = self._extract_candidate_id(container, element)
        if not candidate_id:
            return None

        # ── URL ───────────────────────────────────────────────────────
        url = self._extract_url(container, response.final_url)
        if not url:
            url = response.final_url  # page-level fallback

        # ── Title (clean product name) ────────────────────────────────
        title = self._extract_title(container)
        if not title:
            return None

        # ── Prices ────────────────────────────────────────────────────
        deal_price = self._extract_deal_price(container)
        list_price = self._extract_list_price(container)

        # ── Content snippet (for fingerprinting) ──────────────────────
        content_snippet = container.prettify()

        # ── Confidence ────────────────────────────────────────────────
        confidence = self._calculate_confidence(container, base_confidence)

        return ParsedCandidate(
            candidate_id=candidate_id,
            url=url,
            raw_title=title,  # Clean product name — no price appended
            content_snippet=content_snippet,
            parser_name=self.parser_type,
            confidence_score=confidence,
            source_endpoint_id=response.final_url,
            deal_price=deal_price,
            list_price=list_price,
        )

    # ── Container resolution ──────────────────────────────────────────

    @staticmethod
    def _resolve_card_container(matched_element: Tag) -> Tag | None:
        """Walk upward from the matched element to find the ProductCard wrapper.

        Target: a ``div`` whose class attribute contains
        ``ProductCard-module__``.  Falls back to any div/li/article
        ancestor within 6 levels.
        """
        current = matched_element
        for _ in range(6):
            if current.name == "div":
                cls = current.get("class")
                if cls and any("ProductCard-module__" in c for c in cls):
                    return current
            if current.parent is None:
                break
            current = current.parent

        # Fallback: return the first block-level ancestor
        current = matched_element
        for _ in range(5):
            if current.name in ("div", "li", "article", "section"):
                return current
            if current.parent is None:
                break
            current = current.parent

        return None

    # ── ID extraction ─────────────────────────────────────────────────

    def _extract_candidate_id(
        self, container: Tag, matched_element: Tag
    ) -> str | None:
        """Derive a stable unique identifier."""
        for attr in ("data-promo-id", "data-deal-id", "data-asin"):
            val = container.get(attr) or matched_element.get(attr)
            if val:
                return str(val).strip()

        if container.get("id"):
            return f"id:{container['id']}"

        link = container.find("a", href=True)
        if link and link.get("href"):
            return f"url:{hashlib.md5(link['href'].encode()).hexdigest()[:12]}"

        html = container.prettify()[:500]
        return f"html:{hashlib.md5(html.encode()).hexdigest()[:12]}"

    # ── URL extraction ────────────────────────────────────────────────

    @staticmethod
    def _extract_url(container: Tag, base_url: str) -> str | None:
        """Resolve product URL — ASIN ``/dp/`` links are preferred."""
        for attr in ("data-url", "data-link", "data-href"):
            val = container.get(attr)
            if val:
                return urllib.parse.urljoin(base_url, str(val).strip())

        for selector in HTMLDOMParser.LINK_SELECTORS:
            link = container.select_one(selector)
            if link and link.get("href"):
                return urllib.parse.urljoin(base_url, link["href"].strip())

        return None

    # ── Title extraction ──────────────────────────────────────────────

    @classmethod
    def _extract_title(cls, container: Tag) -> str | None:
        """Extract a clean product title from the card container."""
        for selector in cls.TITLE_SELECTORS:
            elem = container.select_one(selector)
            if elem is None:
                continue

            # For img tags, use the alt attribute
            if elem.name == "img" and elem.get("alt"):
                text = elem["alt"].strip()
                if len(text) > 2:
                    return text

            text = elem.get_text(strip=True)
            if text and len(text) > 2:
                return text

        # Last resort: first substantial text from container
        text = container.get_text(strip=True)
        if text:
            return text[:200]

        return None

    # ── Price extraction ──────────────────────────────────────────────

    @staticmethod
    def _extract_deal_price(container: Tag) -> str | None:
        """Extract the 'With Deal' / current price from ``.a-price .a-offscreen``."""
        span = container.select_one(".a-price .a-offscreen")
        if span is None:
            return None
        raw = span.get_text(strip=True)
        return _PRICE_LABEL_RE.sub("", raw).strip()

    @staticmethod
    def _extract_list_price(container: Tag) -> str | None:
        """Extract the 'List Price' / strikethrough price from ``.a-text-price .a-offscreen``."""
        span = container.select_one(".a-text-price .a-offscreen")
        if span is None:
            return None
        raw = span.get_text(strip=True)
        return _PRICE_LABEL_RE.sub("", raw).strip()

    # ── Confidence scoring ────────────────────────────────────────────

    def _calculate_confidence(
        self, container: Tag, base_confidence: float
    ) -> float:
        """Adjust confidence based on quality signals in the container."""
        confidence = base_confidence

        if container.get("data-promo-id") or container.get("data-deal-id"):
            confidence = min(1.0, confidence + 0.10)
        if container.get("data-asin"):
            confidence = min(1.0, confidence + 0.05)
        if self._extract_title(container):
            confidence = min(1.0, confidence + 0.05)
        if self._extract_url(container, ""):
            confidence = min(1.0, confidence + 0.05)

        text_len = len(container.get_text(strip=True))
        if text_len > 5000:
            confidence *= 0.70
        elif text_len > 2000:
            confidence *= 0.85

        return round(confidence, 2)