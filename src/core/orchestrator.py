"""ScanOrchestrator — the master coordination engine for the Amz-Hunt pipeline."""

from __future__ import annotations

import asyncio
import logging
import random
import time

from src.core.dedup_engine import DedupEngine
from src.core.models.exceptions import AmzHuntError
from src.core.models.parsed_candidate import ParsedCandidate
from src.core.models.promotion import Promotion
from src.core.models.scan_result import ScanOutcome, ScanResult
from src.core.models.target_endpoint import TargetEndpoint
from src.core.notification_queue import NotificationQueue
from src.core.parser_router import ParserRouter
from src.core.ports.http_client import IHttpClient
from src.core.ports.storage import IStorageBackend
from src.core.scheduler import ActiveHoursScheduler
from src.core.validator import KeywordValidator

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    """Master coordination engine that wires the 7-phase Amz-Hunt pipeline.

    Per the Architecture Blueprint (Data Flow & Pipeline), this
    orchestrator executes the full 7-phase scan cycle for each TargetEndpoint:

      Scheduling Gate → HTTP Fetch → Parse → Validate → Dedup → Notify → Log

    Every code path in _process_endpoint returns via a ScanResult logged to
    the IStorageBackend. Exceptions never escape the polling loop — this is
    the global error boundary mandated by the Blueprint.

    Constructor receives all core domain services pre-assembled by the DI
    container. No adapter imports — dependencies arrive as Protocol/abstract
    references only.
    """

    def __init__(
        self,
        storage: IStorageBackend,
        http_client: IHttpClient,
        router: ParserRouter,
        dedup: DedupEngine,
        scheduler: ActiveHoursScheduler,
        validator: KeywordValidator,
        queue: NotificationQueue,
    ) -> None:
        """Initialise the orchestrator with all core domain services.

        Args:
            storage: Persistent storage backend (IStorageBackend Protocol).
            http_client: TLS-impersonated HTTP client (IHttpClient Protocol).
            router: Parser-type dispatcher (ParserRouter).
            dedup: Fingerprint-based dedup engine (DedupEngine).
            scheduler: Active-hours + time-gate scheduler (ActiveHoursScheduler).
            validator: Keyword + confidence validator (KeywordValidator).
            queue: Async notification consumer queue (NotificationQueue).
        """
        self._storage: IStorageBackend = storage
        self._http_client: IHttpClient = http_client
        self._router: ParserRouter = router
        self._dedup: DedupEngine = dedup
        self._scheduler: ActiveHoursScheduler = scheduler
        self._validator: KeywordValidator = validator
        self._queue: NotificationQueue = queue

    async def _process_endpoint(self, endpoint: TargetEndpoint) -> None:
        """Execute the full scan pipeline for a single TargetEndpoint.

        This method is the global error boundary — it ALWAYS returns None
        (never raises). Every outcome is captured as a ScanResult and
        persisted via self._storage.log_scan().

        Pipeline phases:
          1. Scheduler gate (active-hours check)
          2. HTTP fetch (TLS-impersonated)
          3. Status code guard (non-200 → early return)
          4. Parse (dispatcher → IParser.extract_candidates)
          5. Validate + Dedup → Promotion creation
          6. Upsert + Enqueue notification
          7. Log ScanResult

        Args:
            endpoint: The TargetEndpoint to poll. Read-only — scanned state
                (Promotion, ScanResult) is created fresh; mutable fields
                like last_polled_utc are updated via IStorageBackend.
        """
        # ── Phase 1: Scheduler Gate ──
        if not self._scheduler.is_active_now(endpoint):
            logger.debug(
                "Scheduler gate: %s is outside active hours — skipping",
                endpoint.endpoint_id,
            )
            return

        logger.info(
            "Scanning endpoint: %s → %s (parser=%s, impersonate=%s)",
            endpoint.endpoint_id,
            endpoint.url,
            endpoint.parser_type,
            endpoint.impersonate_profile,
        )

        now_utc = time.time()
        discovered: list[Promotion] = []

        try:
            # ── Phase 2: HTTP Fetch ──
            response = await self._http_client.fetch(
                endpoint.url, impersonate=endpoint.impersonate_profile
            )
            logger.info(
                "HTTP %s | %d bytes | %.0fms | TLS=%s",
                response.status_code,
                len(response.body),
                response.latency_ms,
                response.tls_fingerprint_used,
            )

            # ── Phase 3: Status Code Guard ──
            # Defensive: IHttpClient.fetch returns HttpResponse for all status
            # codes (including 403, 429, 502). Parsers expect well-formed
            # content. A non-200 response means we have no structured content
            # to parse — log and return early.
            if response.status_code != 200:
                logger.warning(
                    "Non-200 response for %s: HTTP %s — skipping parse",
                    endpoint.endpoint_id,
                    response.status_code,
                )
                await self._storage.log_scan(
                    ScanResult(
                        endpoint_id=endpoint.endpoint_id,
                        outcome=ScanOutcome.ERROR_PARSE,
                        timestamp_utc=now_utc,
                        http_status_code=response.status_code,
                        error_message=f"Unexpected HTTP {response.status_code}",
                        latency_ms=response.latency_ms,
                        tls_fingerprint_used=response.tls_fingerprint_used,
                    )
                )
                return

            # ── Phase 4: Parse ──
            candidates = await self._router.parse(endpoint, response)
            logger.info(
                "Parsed %d candidate(s) from %s",
                len(candidates),
                endpoint.endpoint_id,
            )

            # ── Phase 5: Validate + Dedup → Promotion Creation ──
            passed = 0
            rejected = 0
            for candidate in candidates:
                if self._validator.is_valid(candidate) and await self._dedup.is_new_promotion(candidate):
                    fingerprint = Promotion.compute_fingerprint(candidate.content_snippet)
                    promotion = Promotion(
                        promo_id=candidate.candidate_id,
                        url=candidate.url,
                        title=candidate.raw_title,
                        content_fingerprint=fingerprint,
                        first_seen_utc=now_utc,
                        source_endpoint_id=endpoint.endpoint_id,
                        deal_price=candidate.deal_price,
                        list_price=candidate.list_price,
                    )

                    # ── Phase 6: Upsert + Enqueue ──
                    await self._storage.upsert_promotion(promotion)
                    await self._queue.enqueue(promotion)
                    discovered.append(promotion)
                    passed += 1
                else:
                    rejected += 1

            logger.info(
                "Validate + Dedup: %d passed, %d rejected → %d NEW promotion(s) discovered",
                passed,
                rejected,
                len(discovered),
            )

            # ── Phase 7: Log Success ──
            outcome = (
                ScanOutcome.SUCCESS_NEW_PROMO
                if discovered
                else ScanOutcome.SUCCESS_NO_CHANGE
            )
            logger.info(
                "Scan complete for %s: %s",
                endpoint.endpoint_id,
                outcome.name,
            )
            await self._storage.log_scan(
                ScanResult(
                    endpoint_id=endpoint.endpoint_id,
                    outcome=outcome,
                    timestamp_utc=now_utc,
                    new_promotions=tuple(discovered),
                    http_status_code=200,
                    latency_ms=response.latency_ms,
                    tls_fingerprint_used=response.tls_fingerprint_used,
                )
            )

        except AmzHuntError as e:
            # Domain-level failure (HttpClientError, ParserError, StorageError,
            # NotificationError, etc.). Structured error → ScanResult, never re-raised.
            # Distinguish connection-level errors from parse-level errors based
            # on the exception type chain.
            outcome = ScanOutcome.ERROR_UNKNOWN
            error_msg = f"{type(e).__name__}: {e}"

            if type(e).__name__ == "HttpClientError":
                outcome = ScanOutcome.ERROR_CONNECTION
            elif type(e).__name__ == "ParserError":
                outcome = ScanOutcome.ERROR_PARSE

            await self._storage.log_scan(
                ScanResult(
                    endpoint_id=endpoint.endpoint_id,
                    outcome=outcome,
                    timestamp_utc=now_utc,
                    error_message=error_msg,
                )
            )
            logger.warning(
                "Domain error scanning %s: %s", endpoint.endpoint_id, error_msg
            )

        except Exception:
            # Belt-and-suspenders catch-all. Anything that escapes the AmzHuntError
            # hierarchy (RuntimeError, asyncio.CancelledError subclasses, etc.) is
            # caught here to guarantee the polling loop never dies.
            logger.exception(
                "Unhandled error scanning %s", endpoint.endpoint_id
            )
            await self._storage.log_scan(
                ScanResult(
                    endpoint_id=endpoint.endpoint_id,
                    outcome=ScanOutcome.ERROR_UNKNOWN,
                    timestamp_utc=now_utc,
                    error_message=f"Unhandled exception — see logs",
                )
            )

    async def run_forever(self, endpoints: list[TargetEndpoint]) -> None:
        """Run the scan pipeline indefinitely over the configured TargetEndpoints.

        Iterates the endpoint list in a round-robin fashion within an infinite
        loop. Each endpoint is processed sequentially via _process_endpoint.
        Anti-bot jitter (random.uniform(45, 75) seconds) is injected between
        endpoint scans to avoid predictable polling intervals that Amazon's
        anomaly detection could flag.

        This coroutine is designed to run as a long-lived asyncio Task.
        Graceful shutdown is achieved by cancelling the Task (CancelledError
        propagates naturally out of the infinite while True).

        Args:
            endpoints: The list of TargetEndpoints to poll. Typically loaded
                from IStorageBackend.get_active_targets() at startup by the
                DI container or entry point.
        """
        cycle = 0
        while True:
            for endpoint in endpoints:
                await self._process_endpoint(endpoint)
                # Anti-bot jitter: break uniform intervals to evade ML-based
                # timing anomaly detection on Amazon's WAF.
                sleep_duration = random.uniform(45, 75)
                logger.info(
                    "Next scan in ~%.0fs (cycle %d, %d endpoint(s))",
                    sleep_duration,
                    cycle,
                    len(endpoints),
                )
                await asyncio.sleep(sleep_duration)
            cycle += 1
