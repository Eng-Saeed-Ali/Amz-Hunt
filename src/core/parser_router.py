"""ParserRouter — dispatches TargetEndpoints to the correct IParser implementation."""

from __future__ import annotations

from src.core.models.exceptions import AmzHuntError
from src.core.models.http_models import HttpResponse
from src.core.models.parsed_candidate import ParsedCandidate
from src.core.models.target_endpoint import TargetEndpoint
from src.core.ports.parser import IParser


class ParserRouter:
    """Routes each TargetEndpoint to its designated parser based on parser_type.

    Accepts a pre-assembled mapping of parser types (e.g., 'html_dom',
    'json_endpoint') to concrete IParser instances. The dependency-injection
    container is responsible for building this mapping; ParserRouter simply
    performs the lookup and dispatches.

    Per Architecture Blueprint Section 3.2, this is the "parse" phase of the
    Orchestrator pipeline: HTTP Response → a list of raw ParsedCandidates.
    """

    def __init__(self, parsers: dict[str, IParser]) -> None:
        """Initialise the router with a mapping of parser type strings to IParser instances.

        Args:
            parsers: A dict where keys are parser_type identifiers (matching
                TargetEndpoint.parser_type) and values are concrete IParser
                implementations.
        """
        self._parsers: dict[str, IParser] = parsers

    async def parse(
        self, endpoint: TargetEndpoint, response: HttpResponse
    ) -> list[ParsedCandidate]:
        """Parse an HTTP response using the endpoint's designated parser.

        Looks up the parser matching endpoint.parser_type, then delegates
        extraction to that parser's extract_candidates method.

        The caller (ScanOrchestrator) is responsible for:
          - Validating that response.status_code is 200 before calling this method.
          - Catching and logging ParserError / AmzHuntError from this call.

        Args:
            endpoint: The TargetEndpoint whose parser_type identifies which
                parser to use. Read-only — never mutated.
            response: The HttpResponse (assumed 200 OK, HTML or JSON body)
                captured by the HTTP client adapter.

        Returns:
            A list of ParsedCandidate objects extracted from the response.
            Returns an empty list ([]) if the parser found no candidates —
            this is a valid (non-error) outcome.

        Raises:
            AmzHuntError: If endpoint.parser_type is not registered in this
                router's parser mapping (misconfiguration).
            ParserError: If the parser raises during extraction (malformed
                HTML, non-JSON body, etc.). Propagated to the orchestrator
                for logging and ScanResult capture.
        """
        parser_type = endpoint.parser_type

        parser = self._parsers.get(parser_type)
        if parser is None:
            raise AmzHuntError(
                f"No parser registered for type '{parser_type}'. "
                f"Endpoint '{endpoint.endpoint_id}' is misconfigured. "
                f"Available parser types: {list(self._parsers.keys())}"
            )

        return await parser.extract_candidates(response)