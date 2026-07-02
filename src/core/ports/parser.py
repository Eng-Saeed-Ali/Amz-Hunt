"""IParser Port — contract for extracting promotion candidates from HTTP responses."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.core.models.exceptions import ParserError
from src.core.models.http_models import HttpResponse
from src.core.models.parsed_candidate import ParsedCandidate


@runtime_checkable
class IParser(Protocol):
    """Abstract interface for extracting promotion candidates from an HTTP response.

    Adapters implementing this Protocol MUST:
      - Accept an HttpResponse (status code 200 is assumed; caller validates).
      - Return a list of ParsedCandidate (empty list if nothing found, NOT None).
      - NEVER raise on non-200 responses (the orchestrator handles response validation
        before passing to the parser).
      - Raise ParserError only when the response body is structurally unparseable
        (e.g., BS4 crashes on severely malformed HTML, or JSON endpoint returns non-JSON).
      - Assign each candidate a confidence_score from 0.0 (uncertain) to 1.0 (certain).

    Multiple parser implementations coexist (HTML DOM parser, JSON endpoint parser),
    discriminated by the parser_type property. The orchestrator's ParserRouter
    dispatches to the correct parser based on the TargetEndpoint's parser_type.
    """

    @property
    def parser_type(self) -> str:
        """Return the parser type identifier string (e.g., "html_dom", "json_endpoint").

        This is used by ParserRouter to route endpoints to the correct parser.
        Must be a constant string for this parser implementation.
        """
        ...

    async def extract_candidates(self, response: HttpResponse) -> list[ParsedCandidate]:
        """Extract promotion candidates from the given HTTP response.

        The response body is assumed to have status_code 200 — the orchestrator
        validates this before calling the parser. The parser should focus purely
        on extraction, not on HTTP semantics.

        Args:
            response: HttpResponse with status_code 200 and HTML/JSON body.

        Returns:
            A list of ParsedCandidate objects. Returns an EMPTY list ([]) if the page
            contains no recognizable promotion elements — this is a valid outcome,
            not an error.

        Raises:
            ParserError: If the response body cannot be parsed structurally
                         (e.g., HTML is so malformed that BS4 raises, or JSON endpoint
                         returns non-JSON content).
        """
        ...