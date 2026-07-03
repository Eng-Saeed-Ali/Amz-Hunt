# Agent_Handoff.md — Phase 2 Completion → Phase 3 Bridge

## - [x] Phase 1 Completed: Summary of Deliverables

### 1. Directory Scaffolding

Full directory tree created per Architecture_Blueprint Section 4. All packages contain `__init__.py` files:

```
Amz-Hunt/
├── Architecture_Blueprint.md        (source of truth — untouched)
├── Agent_Handoff.md                 ← THIS FILE
├── .gitignore
├── data/                            (runtime SQLite DB target + .gitkeep)
│   └── .gitkeep
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── promotion.py         (frozen, slots — Promotion entity)
│   │   │   ├── target_endpoint.py   (slots, mutable state fields)
│   │   │   ├── scan_result.py       (frozen, slots — ScanOutcome enum + ScanResult)
│   │   │   ├── notification.py      (frozen, slots — NotificationResult)
│   │   │   ├── http_models.py       (frozen, slots — HttpResponse)
│   │   │   ├── parsed_candidate.py  (frozen, slots — ParsedCandidate)
│   │   │   └── exceptions.py        (AmzHuntError hierarchy)
│   │   ├── ports/
│   │   │   ├── __init__.py
│   │   │   ├── http_client.py       (IHttpClient Protocol)
│   │   │   ├── storage.py           (IStorageBackend Protocol)
│   │   │   ├── notification.py      (INotificationService Protocol)
│   │   │   └── parser.py            (IParser Protocol)
│   │   └── orchestrator.py          (PLACEHOLDER — Phase 3)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── http/
│   │   │   ├── __init__.py
│   │   │   ├── curl_cffi_client.py  (IMPLEMENTED — Phase 2)
│   │   │   └── header_pool.py       (IMPLEMENTED — Phase 2)
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── sqlite_backend.py    (IMPLEMENTED — Phase 2)
│   │   │   └── migrations.py        (IMPLEMENTED — Phase 2)
│   │   ├── notification/
│   │   │   ├── __init__.py
│   │   │   └── telegram_bot.py      (IMPLEMENTED — Phase 2)
│   │   └── parsers/
│   │       ├── __init__.py
│   │       ├── html_dom_parser.py    (IMPLEMENTED — Phase 2)
│   │       └── json_endpoint_parser.py (IMPLEMENTED — Phase 2)
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py              (PLACEHOLDER — Phase 3)
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                (PLACEHOLDER — Phase 3)
│       └── url_utils.py             (PLACEHOLDER — Phase 3)
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   └── __init__.py
│   └── integration/
│       └── __init__.py
├── scripts/
│   └── __init__.py
└── docs/
    └── __init__.py
```

### 2. Core Domain Models (7 files)

All entities implemented with strict immutability and slots for memory efficiency:

| File | Class(es) | Immutable? | Slots? |
|------|-----------|------------|--------|
| `promotion.py` | `Promotion` | Yes (`frozen=True`) | Yes |
| `target_endpoint.py` | `TargetEndpoint` | No (polling state mutable) | Yes |
| `scan_result.py` | `ScanOutcome` (enum) + `ScanResult` | Yes | Yes |
| `notification.py` | `NotificationResult` | Yes | Yes |
| `http_models.py` | `HttpResponse` | Yes | Yes |
| `parsed_candidate.py` | `ParsedCandidate` | Yes | Yes |
| `exceptions.py` | `AmzHuntError` hierarchy (5 subclasses) | N/A | N/A |

### 3. Port Interfaces (4 files)

All Ports are implemented as `typing.Protocol` with `@runtime_checkable` decorator:

| File | Protocol | Key Methods |
|------|----------|-------------|
| `http_client.py` | `IHttpClient` | `fetch()`, `rotate_fingerprint()`, `session_metrics()` |
| `storage.py` | `IStorageBackend` | `upsert_promotion()`, `get_active_targets()`, `record_failure()`, `log_scan()`, etc. (10 methods) |
| `notification.py` | `INotificationService` | `send_promo_alert()`, `send_health_check()`, `send_error_alert()` |
| `parser.py` | `IParser` | `parser_type` (property), `extract_candidates()` |

---

## - [x] Phase 2 Completed: Concrete Adapter Implementations

### Summary of Implemented Adapters

| Adapter | File | Protocol | Key Features |
|---------|------|----------|--------------|
| **Storage** | `src/adapters/storage/sqlite_backend.py` | `IStorageBackend` | `aiosqlite` async, WAL mode, idempotent migrations (v1), connection pooling via single connection, all 10 protocol methods, `StorageError` wrapping |
| **Storage Migrations** | `src/adapters/storage/migrations.py` | — | Schema: promotions (UNIQUE fingerprint), target_endpoints, scan_log (append-only), schema_version table |
| **HTTP Client** | `src/adapters/http/curl_cffi_client.py` | `IHttpClient` | Session pool keyed by impersonate profile, TLS fingerprint impersonation (Chrome/Firefox/Safari/Edge), header rotation integration, latency measurement, `HttpClientError` wrapping |
| **Header Pool** | `src/adapters/http/header_pool.py` | — | 5 browser profiles, shuffled rotation, Sec-CH-UA Client Hints, Sec-Fetch-*, Egypt/US/Arabic locales, Amazon Egypt referrers |
| **HTML DOM Parser** | `src/adapters/parsers/html_dom_parser.py` | `IParser` (`html_dom`) | BeautifulSoup4 + lxml, 23 CSS selector patterns (data-promo-id=1.0, badges=0.85, IDs=0.75, classes=0.55), DOM walk-up to semantic containers, URL resolution, dynamic confidence scoring, `ParserError` wrapping |
| **JSON Endpoint Parser** | `src/adapters/parsers/json_endpoint_parser.py` | `IParser` (`json_endpoint`) | Standard `json` module, 12 known Amazon AJAX paths, 7 ID/title/URL field mappings, two-phase discovery (known paths → broad heuristic search), `ParserError` wrapping |
| **Telegram Notifier** | `src/adapters/notification/telegram_bot.py` | `INotificationService` | Raw `aiohttp` to Telegram Bot API, HTML parse mode, exponential backoff (250ms→500ms→1s→2s→4s, 5 retries), 429/5xx retry logic with `retry_after`, web preview disabled, `NotificationError` wrapping |

### Phase 2 Validation Checklist — ALL COMPLETE ✅

- [x] `sqlite_backend.py` passes `isinstance(sqlite_backend, IStorageBackend)` (runtime_checkable)
- [x] `curl_cffi_client.py` implements full `IHttpClient` protocol with session pooling
- [x] `html_dom_parser.py` extracts `ParsedCandidate` from Amazon-like HTML with confidence scoring
- [x] `telegram_bot.py` implements full `INotificationService` with exponential backoff retries
- [x] All adapter errors inherit from correct `AmzHuntError` subclass (`StorageError`, `HttpClientError`, `ParserError`, `NotificationError`)
- [x] SQLite database created at configurable path (`data/amz_hunt.db` default)

### Files NOT Touched in Phase 2 (Per Contract)

- `src/core/**` — All core models and ports remain frozen from Phase 1
- `Architecture_Blueprint.md` — Source of truth, reference only
- `src/core/orchestrator.py` — Phase 3 territory
- `src/config/settings.py`, `src/utils/logger.py`, `src/utils/url_utils.py` — Phase 3

---

## - [ ] Architectural Notes for the Next Agent (Phase 3)

### Immutability Rules — DO NOT BREAK THESE

1. **Frozen models are never modified after creation.** The orchestrator creates new instances when state changes. For example, to mark a `ScanResult` with discovered promotions, create a new `ScanResult` — do NOT try to mutate the tuple.

2. **`TargetEndpoint` is the ONLY mutable model.** Its `last_polled_utc`, `consecutive_failures`, and `circuit_breaker_until_utc` fields are mutated by the orchestrator and persisted by `IStorageBackend`. The `active_hours` tuple defaults to `(6, 0)` — that's 06:00–00:00 UTC (= 08:00–02:00 Cairo local). Every other field should be treated as configuration-immutable after initial load.

3. **`Promotion` equality is based on `promo_id`** (though `@dataclass(frozen=True)` generates equality across all fields — the dedup engine in Phase 3 will use `content_fingerprint` for fingerprint-based dedup via `IStorageBackend.get_promotion_by_fingerprint()`).

4. **`ScanResult.new_promotions` is a `tuple`, not a `list`.** For zero-allocation empty results, use `()` — the default value is already set.

### Typing and Import Rules

5. **All models use `from __future__ import annotations`** — this enables PEP 604 union syntax (`int | None` instead of `Optional[int]`). All models are Python 3.11+ compatible.

6. **`ScanResult` uses `TYPE_CHECKING` guard** for the `Promotion` import in its type annotation to avoid circular imports at runtime. The `# type: ignore[name-defined]` comment is intentional and required.

7. **All Ports use `Protocol` from `typing`, not `ABC` from `abc`.** This is a deliberate choice from the Blueprint (Section 1.2): Protocols provide structural subtyping with zero runtime overhead. Adapters do NOT need to inherit from the Protocol — they just need to satisfy the method signatures.

8. **`from __future__ import annotations` is used in Ports** — this makes all annotations lazily evaluated, preventing import-time circular dependencies between Port modules and Model modules.

### Exception Handling Contract

9. **Domain exceptions form a strict hierarchy:** `AmzHuntError` → `HttpClientError`, `StorageError`, `NotificationError`, `ParserError`, `ValidationError`. All adapter-level exceptions MUST inherit from the appropriate domain exception. Generic Python exceptions (like `RuntimeError`, `ValueError`) must NEVER leak from adapter code — catch and wrap them.

10. **The orchestrator's global error boundary catches `AmzHuntError` only.** Any adapter that raises a non-`AmzHuntError` exception will crash the polling loop. This is a hard contract.

---

## - [ ] Next Steps for Phase 3: Core Orchestration & Entry Point

### Priority Order (Build in This Sequence)

#### 1. `src/core/dedup_engine.py` — HIGHEST PRIORITY
Implement the deduplication engine that bridges parsers and storage.

**Key responsibilities:**
- `process_candidates(storage, candidates, validator)` → `list[Promotion]`
- Filter candidates: `confidence_score >= 0.6` (validator threshold)
- For each qualifying candidate:
  - Compute `content_fingerprint = Promotion.compute_fingerprint(candidate.content_snippet)`
  - Check `storage.get_promotion_by_fingerprint(fingerprint)`
  - If EXISTS → update `last_seen_utc` silently, skip
  - If NEW → create `Promotion` entity, call `storage.upsert_promotion()`
- Return list of genuinely NEW promotions (where `upsert_promotion()` returned `True`)

**Two-layer dedup (per Blueprint):**
| Layer | Check | Purpose |
|-------|-------|---------|
| Fingerprint Match | SHA256 of content snippet | Same promo, same page structure — don't re-alert even if URL changed |
| Promotion ID Match | `promo_id` from Amazon's `data-promo-id` | Amazon's own unique identifier — ultimate authority |

#### 2. `src/core/validator.py` — HIGH PRIORITY
Implement keyword + DOM pattern validation per Blueprint Section 2.3.

**Validation logic:**
```
confidence_score = 0.0
+ 0.3 if ANY Arabic keyword in title/nearby text (خصم, عرض, تخفيضات, صفقة, كوبون, توفير)
+ 0.3 if ANY English keyword in title/nearby text (deal, coupon, offer, sale, discount, promo)
+ 0.4 if ANY DOM pattern matched ([class*="dealBadge"], [data-promo-id], etc.)
Candidate passes if confidence_score >= 0.6
```

#### 3. `src/core/scheduler.py` — HIGH PRIORITY
Implement `ActiveHoursScheduler` for target selection with jitter and time-of-day logic.

**Key methods:**
- `select_next_target(storage: IStorageBackend, now_utc: float) -> TargetEndpoint | None`
- `is_within_active_hours(now_utc: float, active_window: tuple[int, int]) -> bool`
- Jitter formula: `effective_interval = poll_interval + random.uniform(-15, +15)`
- Active hours: Cairo UTC+2 → configure as `(6, 0)` UTC = 08:00–02:00 Cairo
- During inactive hours: slow scan mode (5–10 min intervals)
- Circuit breaker check: skip if `endpoint.is_in_cooldown(now_utc)`

#### 4. `src/core/parser_router.py` — HIGH PRIORITY
Simple dispatcher: `endpoint.parser_type` → `IParser` instance.

**Methods:**
- `register(parser_type: str, parser: IParser)`
- `get(parser_type: str) -> IParser | None`
- Pre-register `"html_dom"` → `HTMLDOMParser()`, `"json_endpoint"` → `JSONEndpointParser()`

#### 5. `src/core/notification_queue.py` — HIGH PRIORITY
Async queue consumer with retry/backoff for Telegram dispatch.

**Key responsibilities:**
- `asyncio.Queue[tuple[Promotion, int]]` — (promo, retry_count)
- Consumer task: `await queue.get()`, call `notifier.send_promo_alert()`
- On success: `storage.mark_alert_sent(promo_id)`
- On failure: if `retry_count < 3`, requeue with `2**retry_count` seconds delay
- On exhaustion: log error, call `notifier.send_error_alert()`

#### 6. `src/core/orchestrator.py` — CORE PRIORITY
The `ScanOrchestrator` — master coordination logic.

**Constructor:**
```python
ScanOrchestrator(
    http: IHttpClient,
    storage: IStorageBackend,
    notifier: INotificationService,
    parsers: ParserRouter,
    scheduler: ActiveHoursScheduler,
    dedup: DedupEngine,
    validator: KeywordValidator,
    notification_queue: NotificationQueue,
)
```

**Main loop (`run_forever()`):**
1. `shutdown_flag = asyncio.Event()` (set by signal handler)
2. While not shutdown:
   - `target = await scheduler.select_next_target(storage, now)`
   - If None → `await asyncio.sleep(5)`, continue
   - `await poll_single_endpoint(target, now)` (with global error boundary)
   - `await asyncio.sleep(effective_interval_with_jitter)`

**Global error boundary (`poll_single_endpoint`):**
- Every code path returns `ScanResult` — NEVER raises
- Circuit breaker gate → HTTP fetch → Status code routing → Parse → Validate/Dedup → Queue notification → Log scan
- See Blueprint Section 5.1 for full pseudocode

#### 7. `src/core/di_container.py` — COMPOSITION ROOT
Assembles all adapters and wires dependencies.

**Responsibilities:**
- Load config from `src.config.settings` (Phase 3)
- Instantiate: `CurlCffiClient`, `SQLiteBackend`, `TelegramBotNotifier`, `HTMLDOMParser`, `JSONEndpointParser`
- Build `ParserRouter` with both parsers
- Create `ActiveHoursScheduler`, `DedupEngine`, `KeywordValidator`, `NotificationQueue`
- Construct `ScanOrchestrator` with all dependencies
- Return orchestrator instance

#### 8. `src/config/settings.py` — CONFIGURATION
Pydantic-based Settings model loading from `.env`:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `DATABASE_PATH` (default: `data/amz_hunt.db`)
- `DEFAULT_IMPERSONATE_PROFILE` (default: `chrome124`)
- `LOG_LEVEL` (default: `INFO`)

#### 9. `scripts/seed_targets.py` — DB SEEDING
Reads `src/config/target_registry.py` (curated `TargetEndpoint` list) and upserts into SQLite.

#### 10. `scripts/run_monitor.py` — ENTRY POINT
```python
# Single command: python -m scripts.run_monitor
async def main():
    container = DIContainer()
    orchestrator = await container.build()
    await orchestrator.run_forever()
```

#### 11. `src/core/shutdown.py` — GRACEFUL SHUTDOWN
SIGTERM/SIGINT handler → set shutdown flag → wait for in-flight polls (max 30s) → drain notification queue (10s timeout) → close DB → log final metrics.

---

### Phase 3 Validation Checklist

Before considering Phase 3 complete:
- [ ] `dedup_engine.py` correctly implements two-layer dedup (fingerprint + promo_id)
- [ ] `validator.py` applies Arabic/English keyword + DOM pattern scoring
- [ ] `scheduler.py` handles jitter, active hours, circuit breaker, slow-scan mode
- [ ] `parser_router.py` dispatches correctly for both parser types
- [ ] `notification_queue.py` retries with backoff, marks alert_sent on success
- [ ] `orchestrator.py` has global error boundary returning `ScanResult` for ALL paths
- [ ] `di_container.py` assembles all adapters without importing them in core logic
- [ ] `settings.py` loads from `.env` with sensible defaults
- [ ] `seed_targets.py` populates DB from curated registry
- [ ] `run_monitor.py` is the single entry point
- [ ] `shutdown.py` handles SIGTERM/SIGINT gracefully
- [ ] Integration tests pass: full pipeline from fetch → parse → dedup → notify → log

---

*Generated by Phase 2 Adapter Implementation Agent — ready for Phase 3 Core Orchestration.*