"""JSON endpoint parser adapter — implements IParser for AJAX/XHR promo data."""

from __future__ import annotations

import json
import hashlib
import urllib.parse
from typing import TYPE_CHECKING

from src.core.models.exceptions import ParserError
from src.core.models.http_models import HttpResponse
from src.core.models.parsed_candidate import ParsedCandidate
from src.core.ports.parser import IParser

if TYPE_CHECKING:
    from collections.abc import Iterable


class JSONEndpointParser:
    """JSON parser for Amazon Egypt AJAX/XHR promotional endpoints.

    Parses structured JSON responses from Amazon's internal APIs
    (e.g., deal widgets, promotion feeds, personalized recommendations).

    Implements IParser protocol with parser_type = "json_endpoint".
    """

    # Known Amazon AJAX response paths containing promo arrays
    # Ordered by likelihood — first match wins
    PROMO_PATHS: list[str] = [
        "deals",
        "promotions",
        "data.deals",
        "data.promotions",
        "response.deals",
        "response.promotions",
        "widgets",
        "results",
        "items",
        "products",
        "dealItems",
        "promoItems",
    ]

    # Field mappings for extracting promo data from JSON objects
    ID_FIELDS: list[str] = [
        "id",
        "promoId",
        "dealId",
        "promotionId",
        "asin",
        "deal_id",
        "promo_id",
    ]

    TITLE_FIELDS: list[str] = [
        "title",
        "name",
        "dealTitle",
        "promoTitle",
        "displayName",
        "headline",
        "label",
    ]

    URL_FIELDS: list[str] = [
        "url",
        "link",
        "dealUrl",
        "promoUrl",
        "landingUrl",
        "href",
        "clickUrl",
        "destinationUrl",
    ]

    @property
    def parser_type(self) -> str:
        """Return the parser type identifier."""
        return "json_endpoint"

    async def extract_candidates(self, response: HttpResponse) -> list[ParsedCandidate]:
        """Extract promotion candidates from JSON response.

        Args:
            response: HttpResponse with JSON body (status_code assumed 200).

        Returns:
            List of ParsedCandidate objects. Empty list if no matches found.

        Raises:
            ParserError: If response body is not valid JSON.
        """
        if not response.body or not response.body.strip():
            return []

        # Parse JSON
        try:
            data = json.loads(response.body)
        except json.JSONDecodeError as e:
            raise ParserError(f"Invalid JSON in response: {e}") from e

        candidates: list[ParsedCandidate] = []
        seen_fingerprints: set[str] = set()

        # Find promo arrays in the JSON structure
        promo_arrays = self._find_promo_arrays(data)

        for promo_array in promo_arrays:
            for item in promo_array:
                if not isinstance(item, dict):
                    continue

                candidate = self._extract_from_json_object(
                    item=item,
                    response=response,
                )
                if candidate:
                    # Dedup by content fingerprint within this parse
                    fp = hashlib.sha256(
                        candidate.content_snippet.strip().lower().encode("utf-8")
                    ).hexdigest()
                    if fp not in seen_fingerprints:
                        seen_fingerprints.add(fp)
                        candidates.append(candidate)

        return candidates

    def _find_promo_arrays(self, data: object) -> list[list[dict]]:
        """Recursively find arrays of promo objects in the JSON data."""
        arrays: list[list[dict]] = []

        # Try known paths first
        for path in self.PROMO_PATHS:
            value = self._get_nested_value(data, path)
            if isinstance(value, list) and value:
                # Filter to dict objects only
                dict_items = [v for v in value if isinstance(v, dict)]
                if dict_items:
                    arrays.append(dict_items)

        # If no known paths matched, do a broader search
        if not arrays:
            arrays.extend(self._broad_search(data))

        return arrays

    def _get_nested_value(self, obj: object, path: str) -> object:
        """Get nested value from object using dot notation path."""
        current = obj
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                # Try to parse key as index
                try:
                    idx = int(key)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                except ValueError:
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    def _broad_search(self, obj: object, depth: int = 0) -> list[list[dict]]:
        """Recursively search for arrays of dict objects that look like promos."""
        if depth > 5:  # Limit recursion depth
            return []

        arrays: list[list[dict]] = []

        if isinstance(obj, dict):
            for value in obj.values():
                arrays.extend(self._broad_search(value, depth + 1))
        elif isinstance(obj, list):
            # Check if this list contains dict objects with promo-like fields
            dict_items = [v for v in obj if isinstance(v, dict)]
            if dict_items and self._looks_like_promos(dict_items):
                arrays.append(dict_items)
            # Also recurse into each item
            for item in obj:
                arrays.extend(self._broad_search(item, depth + 1))

        return arrays

    def _looks_like_promos(self, items: list[dict]) -> bool:
        """Heuristic: check if dict objects have promo-like fields."""
        if not items:
            return False

        # Check first few items for promo-like fields
        sample_size = min(3, len(items))
        promo_field_count = 0

        for item in items[:sample_size]:
            if not isinstance(item, dict):
                continue

            # Check for ID fields
            has_id = any(field in item for field in self.ID_FIELDS)
            # Check for title fields
            has_title = any(field in item for field in self.TITLE_FIELDS)
            # Check for URL fields
            has_url = any(field in item for field in self.URL_FIELDS)

            if has_id or has_title or has_url:
                promo_field_count += 1

        return promo_field_count >= sample_size * 0.5  # At least half have promo fields

    def _extract_from_json_object(
        self,
        item: dict,
        response: HttpResponse,
    ) -> ParsedCandidate | None:
        """Extract a ParsedCandidate from a JSON promo object."""
        # Extract candidate_id
        candidate_id = self._extract_id(item)
        if not candidate_id:
            return None

        # Extract URL
        url = self._extract_url(item, response.final_url)
        if not url:
            url = response.final_url  # Fallback

        # Extract title
        title = self._extract_title(item)
        if not title:
            return None

        # Content snippet for fingerprinting (the JSON object itself)
        content_snippet = json.dumps(item, ensure_ascii=False, sort_keys=True)

        # Confidence score for structured JSON (high but not perfect)
        confidence = 0.9

        # Use response.final_url as source_endpoint_id
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

    def _extract_id(self, item: dict) -> str | None:
        """Extract candidate ID from JSON object."""
        for field in self.ID_FIELDS:
            val = item.get(field)
            if val is not None:
                return str(val).strip()

        # Fallback: hash of the object
        obj_str = json.dumps(item, sort_keys=True)[:500]
        return f"json:{hashlib.md5(obj_str.encode()).hexdigest()[:12]}"

    def _extract_url(self, item: dict, base_url: str) -> str | None:
        """Extract and resolve URL from JSON object."""
        for field in self.URL_FIELDS:
            val = item.get(field)
            if val and isinstance(val, str):
                return urllib.parse.urljoin(base_url, val.strip())

        return None

    def _extract_title(self, item: dict) -> str | None:
        """Extract title from JSON object."""
        for field in self.TITLE_FIELDS:
            val = item.get(field)
            if val and isinstance(val, str):
                text = val.strip()
                if text and len(text) > 2:
                    return text

        return None