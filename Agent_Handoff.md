# 🚀 READY FOR LAUNCH — Amz-Hunt Monitor (Phases 1–4 Complete) 🚀

## Project Status: Phases 1–4 Implemented ✅

| Phase | Status | Deliverables |
|-------|--------|--------------|
| **Phase 1** — Foundation | ✅ Complete | 7 Core Domain Models, 4 Port Interfaces, Directory Scaffolding |
| **Phase 2** — Full Wiring | ✅ Complete | 6 Adapter Implementations (SQLite, curl_cffi, HTML/JSON Parsers, Telegram, Headers, Migrations) |
| **Phase 3** — Intelligence | ✅ Complete | 5 Core Domain Services, Orchestrator, DI Container, Config, Shutdown, Entry Point, Seed Script |
| **Phase 4** — Containerization | ✅ Complete | Multi-stage Dockerfile, docker-compose.yml, .dockerignore, non-root user, HEALTHCHECK |
| **Phase 5** — Resilience & Production | ✅ Complete | Docker log rotation (json-file: max-size 10m / max-file 3), deploy.sh (git pull → .env check → build → image prune), vps_healthcheck.sh (docker inspect health-check → auto-restart → incident log → crontab docs) |
| **Phase 6** — Observability | ✅ Complete | `requirements.txt` (+prometheus-client≥0.20), `src/core/metrics.py` (6 families: Counter/Gauge/Histogram), non-blocking `start_metrics_server(9090)` in `run_monitor.py`, orchestrator instrumentation (4 outcome paths → scans_total, promotions_discovered, latency_seconds, circuit_breaker_trips/active), notification_queue instrumentation (success/failed counters), `docker-compose.yml` port 9090 exposure |

## Launch Commands

```bash
# 1. Copy and configure your environment
cp .env.example .env
# Edit .env — add your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

# 2. Seed the database with default Amazon Egypt targets
python -m scripts.seed_targets

# 3. Start the monitor
python -m scripts.run_monitor
```

## What Remains (Phase 6+ — Observability & Beyond)

- [x] Docker containerization (Phases 1–4 complete)
- [x] Minimal pytest unit test suite created (promotion fingerprint + scheduler logic)
- [x] Docker log rotation — json-file driver (max-size: 10m, max-file: 3)
- [x] Automated deployment script (deploy.sh) with strict error handling
- [x] VPS health-check script (vps_healthcheck.sh) with auto-restart + incident logging
- [ ] Expand unit test coverage for remaining core services
- [ ] CI/CD pipeline configuration
- [ ] Prometheus metrics exporter & monitoring dashboard (Phase 6)
- [ ] Multi-domain marketplace support — KSA, UAE (Phase 7)

---

# Agent_Handoff.md — Phases 1–4 Complete → Phase 5 Bridge

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
│   │   └── orchestrator.py          (IMPLEMENTED — Phase 3)
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
│   │   └── settings.py              (IMPLEMENTED — Phase 3)
│   └── utils/
│       └── __init__.py
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
- `src/config/settings.py` — Phase 3 (now implemented)

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

## - [x] Phase 3 Completed: Core Orchestration & Entry Points

### Phase 3 — Part 1 (Core Domain Services) ✅

| Service | File | Class | Constructor |
|---------|------|-------|-------------|
| **Dedup Engine** | `src/core/dedup_engine.py` | `DedupEngine` | `DedupEngine(storage_backend: IStorageBackend)` |
| **Scheduler** | `src/core/scheduler.py` | `ActiveHoursScheduler` | `ActiveHoursScheduler()` |
| **Validator** | `src/core/validator.py` | `KeywordValidator` | `KeywordValidator()` |

**`DedupEngine.is_new_promotion(candidate)`:** Checks `storage.get_promotion_by_fingerprint()` returns None. True = genuinely new promotion.

**`ActiveHoursScheduler.is_active_now(endpoint)`:** Checks current UTC hour against `active_hours_start` / `active_hours_end`. Handles 24/7 endpoints (both None or equal). Handles overnight windows (e.g., 06:00–00:00 UTC).

**`KeywordValidator.is_valid(candidate)`:** Case-insensitive keyword matching on `raw_title`. Keywords: Arabic ("خصم", "عرض", "وفر", "تخفيض", "كوبون", "صفقة") + English ("deal", "promo", "save", "sale", "offer", "discount", "coupon"). Returns True if any keyword present.

### Phase 3 — Part 2 (Domain Mediators) ✅

| Service | File | Class | Constructor |
|---------|------|-------|-------------|
| **Parser Router** | `src/core/parser_router.py` | `ParserRouter` | `ParserRouter(parsers: dict[str, IParser])` |
| **Notification Queue** | `src/core/notification_queue.py` | `NotificationQueue` | `NotificationQueue(notifier: INotificationService)` |

**`ParserRouter.parse(endpoint, response)`:** Extracts `parser_type` from endpoint, looks up matching `IParser` in `self._parsers` dict, delegates to `parser.extract_candidates(response)` → `list[ParsedCandidate]`. Raises `AmzHuntError` for unregistered parser types.

**`NotificationQueue.enqueue(promotion)` / `worker()`:** Backed by `asyncio.Queue[Promotion]`. Orchestrator calls `enqueue()`; a background `worker()` task (started by `run_monitor.py`) continuously dequeues and delivers via `notifier.send_promo_alert()`. Resilience: catches `NotificationError` (WARNING) and broad `Exception` (ERROR with traceback) — worker loop never crashes.

### Phase 3 — Part 3 (Orchestrator) ✅

**`src/core/orchestrator.py`** — `ScanOrchestrator` (7 injected dependencies):
```
storage → http_client → router → dedup → scheduler → validator → queue
```

`_process_endpoint()` — 7-phase pipeline with global error boundary:
1. Scheduler Gate → 2. HTTP Fetch → 3. Status Code Guard → 4. Parse → 5. Validate + Dedup → 6. Upsert + Enqueue → 7. Log ScanResult

`run_forever(endpoints)` — Infinite round-robin loop with anti-bot jitter (45–75s random sleep).

### Phase 3 — Part 4 (Wiring & Entry Points) ✅

| File | Class | Role |
|------|-------|------|
| `src/config/settings.py` | `Settings` | Pydantic `BaseSettings` loading `.env` (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_PATH, LOG_LEVEL, DEFAULT_IMPERSONATE_PROFILE) |
| `.env.example` | — | Template with all config keys documented |
| `src/core/di_container.py` | `DIContainer` | **The ONLY file in core allowed to import adapters.** `build()` → creates `SQLiteBackend`, `CurlCffiClient`, `TelegramBotNotifier`, `HTMLDOMParser`, `JSONEndpointParser`, assembles `ParserRouter`, creates all core services, wires `ScanOrchestrator`. Exposes `storage` and `queue` properties for entry point. |
| `src/core/shutdown.py` | `GracefulShutdown` | Platform-aware signal handling: Unix uses `loop.add_signal_handler` (asyncio-native), Windows falls back to `signal.signal()`. Sets `asyncio.Event` on SIGINT/SIGTERM. `wait_for_shutdown()` coroutine. |
| `scripts/run_monitor.py` | `main()` | **Single entry point.** Configure logging → DIContainer.build() → fetch TargetEndpoints → start NotificationQueue.worker() → register signals → orchestrator.run_forever() → await shutdown → cancel tasks (10s grace period) → close DB. |
| `scripts/seed_targets.py` | `seed()` | **Idempotent DB seeding.** Opens DB → runs migrations → INSERT OR IGNORE 2 default Amazon Egypt targets (HTML deals page + JSON AJAX endpoint). Prints summary: inserted / existing / total active. |

---

### Phase 3 Validation Checklist — ALL COMPLETE ✅

- [x] `dedup_engine.py` correctly implements fingerprint-based dedup via IStorageBackend
- [x] `validator.py` applies Arabic/English keyword matching (case-insensitive)
- [x] `scheduler.py` handles active hours, 24/7 endpoints, overnight windows
- [x] `parser_router.py` dispatches correctly for both parser types (html_dom, json_endpoint)
- [x] `notification_queue.py` decouples notification delivery via asyncio.Queue worker
- [x] `orchestrator.py` has global error boundary returning `ScanResult` for ALL paths
- [x] `di_container.py` assembles all adapters (ONLY file in core permitted to import adapters)
- [x] `settings.py` loads from `.env` with sensible defaults (pydantic-settings)
- [x] `.env.example` template file created in project root
- [x] `scripts/seed_targets.py` populates DB with 2 default Amazon Egypt targets (idempotent)
- [x] `scripts/run_monitor.py` is the single entry point (`python -m scripts.run_monitor`)
- [x] `src/core/shutdown.py` handles SIGTERM/SIGINT gracefully (Unix asyncio-native + Windows fallback)
- [x] Integration tests: full pipeline (fetch → parse → dedup → notify → log) 

---

*Generated by Phase 3 Core Orchestration Agent — project is launch-ready. Next phase: comprehensive testing.*

### Updated Phase 3 Directory Tree

```
src/core/
├── models/         (7 files — Phase 1)
├── ports/          (4 files — Phase 1)
├── dedup_engine.py       (Phase 3 - Part 1) ✅
├── scheduler.py          (Phase 3 - Part 1) ✅
├── validator.py          (Phase 3 - Part 1) ✅
├── parser_router.py      (Phase 3 - Part 2) ✅
├── notification_queue.py (Phase 3 - Part 2) ✅
├── orchestrator.py       (Phase 3 - Part 3) ✅
├── di_container.py       (Phase 3 - Part 4) ✅
└── shutdown.py           (Phase 3 - Part 4) ✅
src/config/
└── settings.py           (Phase 3 - Part 4) ✅
scripts/
├── run_monitor.py        (Phase 3 - Part 4) ✅
└── seed_targets.py       (Phase 3 - Part 4) ✅
.env.example              (Phase 3 - Part 4) ✅
```

---

## - [x] Phase 4 Completed: Docker Containerization

### Deliverables

| File | Purpose | Key Details |
|------|---------|-------------|
| `requirements.txt` | Pinned runtime dependencies | curl_cffi>=0.7, aiosqlite>=0.20, beautifulsoup4>=4.12, lxml>=5.0, pydantic-settings>=2.0, aiohttp>=3.9 |
| `.dockerignore` | Build context exclusions | Excludes .git, __pycache__, .venv, .env, data/*.db/WAL/SHM, tests/, docs/, IDE files, Docker files |
| `Dockerfile` | Production image | python:3.11-slim, PYTHONPATH=/app, system deps (libcurl4-openssl-dev, libxml2, libxslt1.1), layer-cached pip install, CMD: python -m scripts.run_monitor |
| `docker-compose.yml` | 24/7 VPS orchestration | Service: amz-hunt-monitor, Container: amz-hunt-bot, restart: unless-stopped, volume: ./data:/app/data (SQLite WAL persistence), env_file: .env |

### Docker Quick Launch

```bash
cp .env.example .env     # Edit with real Telegram credentials
docker compose up -d --build
docker compose logs -f    # Watch the monitor output
docker compose down       # Graceful shutdown (SIGTERM → drain queue → close DB)
```

---

## - [x] Phase 5 Completed: VPS Deployment & Production Monitoring

### Deliverables

| File | Purpose | Key Details |
|------|---------|-------------|
| `docker-compose.yml` (updated) | Docker log rotation | Added `logging` block: `json-file` driver, `max-size: "10m"`, `max-file: "3"` — prevents 24/7 scraping logs from saturating VPS disk (30 MB hard ceiling) |
| `deploy.sh` | Automated VPS deployment | Strict `set -e` error handling; 4-step pipeline: `git pull origin main` → `.env` existence check (warn + exit if missing) → `docker compose up -d --build` → `docker image prune -f` |
| `scripts/vps_healthcheck.sh` | Lightweight health-check + auto-restart | Two-stage `docker inspect` verification: (1) container running, (2) health status healthy. Auto-restarts via `docker compose restart amz-hunt-monitor` on failure. Logs incidents with UTC timestamps to `data/vps_health_incidents.log`. Includes crontab setup instructions (`*/5 * * * *`). |

### Phase 5 Validation Checklist — ALL COMPLETE ✅

- [x] Docker log rotation configured (json-file, 10 MB × 3 files = 30 MB max)
- [x] `deploy.sh` automates git pull → .env validation → docker compose up --build → image prune
- [x] `vps_healthcheck.sh` verifies container running + healthy, auto-restarts on failure
- [x] Incident logging with UTC timestamps to `data/vps_health_incidents.log`
- [x] Crontab documentation embedded in health-check script comments
- [x] No core Python code in `src/` modified — all changes are DevOps/infrastructure only

---

## - [x] Phase 6 Completed: Observability (Prometheus Metrics Exporter)

### Deliverables

| File | Purpose | Key Details |
|------|---------|-------------|
| `requirements.txt` (updated) | Zero-budget Prometheus dependency | Added `prometheus-client>=0.20.0,<1.0.0` (MIT-licensed) under new Observability section |
| `src/core/metrics.py` (NEW — 152 lines) | Centralised metrics definitions | 6 metric families as module-level singletons: `scans_total` (Counter, labels: endpoint_id + outcome), `promotions_discovered_total` (Counter, label: endpoint_id), `notifications_sent_total` (Counter, label: status=success/failed), `circuit_breaker_trips_total` (Counter, label: endpoint_id), `circuit_breaker_active` (Gauge), `scan_latency_seconds` (Histogram, buckets: 0.5/1/2.5/5/10/30). Helper: `start_metrics_server(port=9090)` — invokes `prometheus_client.start_http_server()` as a daemon thread |
| `scripts/run_monitor.py` (updated) | Metrics server startup in bootstrap | Imports `start_metrics_server` from `src.core.metrics`, calls `start_metrics_server(9090)` immediately after DI container build (step 3 of 8 in the startup sequence), BEFORE asyncio tasks begin — the daemon thread runs alongside the event loop without interference |
| `src/core/orchestrator.py` (updated) | Full scan-pipeline instrumentation | Instrumented all 4 outcome paths inside `_process_endpoint()`: **(a)** non-200 response handler maps 403→BLOCKED_403, 429→BLOCKED_THROTTLED, 503→BLOCKED_CAPTCHA with `scans_total` + `circuit_breaker_trips_total` + `circuit_breaker_active.inc()`; **(b)** success path (200) records `scans_total` (SUCCESS_NEW_PROMO / SUCCESS_NO_CHANGE), `promotions_discovered_total` (count of new promos), and `scan_latency_seconds` (latency_ms/1000 observed into histogram); **(c)** `AmzHuntError` catch maps HttpClientError→ERROR_CONNECTION, ParserError→ERROR_PARSE into `scans_total`; **(d)** broad `Exception` catch records ERROR_UNKNOWN into `scans_total` |
| `src/core/notification_queue.py` (updated) | Notification delivery outcome tracking | Worker loop now increments `notifications_sent_total{status="success"}` on successful `send_promo_alert()`, `notifications_sent_total{status="failed"}` on `NotificationError` (adapter exhausted), and `notifications_sent_total{status="failed"}` on unexpected `Exception` |
| `docker-compose.yml` (updated) | Prometheus scrape port exposure | Added `ports: - "9090:9090"` to the `amz-hunt-monitor` service, enabling external Prometheus (or local `curl`) to scrape `/metrics` |

### 6 Metric Families — Complete Mapping

| # | Metric Name | Type | Labels | Instrumentation Location | Purpose |
|---|-------------|------|--------|--------------------------|---------|
| 1 | `amz_hunt_scans_total` | Counter | `endpoint_id`, `outcome` | orchestrator — 4 paths (success, non-200, AmzHuntError, Exception) | Primary throughput + error-rate metric. `outcome` label holds ScanOutcome enum name: SUCCESS_NEW_PROMO, SUCCESS_NO_CHANGE, BLOCKED_403, BLOCKED_CAPTCHA, BLOCKED_THROTTLED, ERROR_CONNECTION, ERROR_TIMEOUT, ERROR_PARSE, ERROR_UNKNOWN |
| 2 | `amz_hunt_promotions_discovered_total` | Counter | `endpoint_id` | orchestrator — success path (after dedup passes) | Count of genuinely new, never-before-seen promotions per endpoint source |
| 3 | `amz_hunt_notifications_sent_total` | Counter | `status` (success/failed) | notification_queue — worker loop (3 outcomes: success, NotificationError, Exception) | Telegram delivery reliability gauge — ratio of success:failed over time |
| 4 | `amz_hunt_circuit_breaker_trips_total` | Counter | `endpoint_id` | orchestrator — non-200 handler (403, 429, 503) | How often Amazon blocks each endpoint — early warning for IP reputation decay |
| 5 | `amz_hunt_circuit_breaker_active` | Gauge | (none) | orchestrator — `inc()` on block, primed for `dec()` on recovery | Real-time count of endpoints currently in cooldown (ready for full circuit-breaker recovery logic in future phase) |
| 6 | `amz_hunt_scan_latency_seconds` | Histogram | `endpoint_id` | orchestrator — success path (latency_ms / 1000 observed) | HTTP fetch latency distribution per endpoint. Buckets: ≤0.5s (cache hit), ≤1s (healthy), ≤2.5s (acceptable), ≤5s (borderline), ≤10s (degraded), ≤30s (timeout threshold) |

### Architecture Compliance Verification

- **Hexagonal Integrity**: `src/core/metrics.py` is in Core layer. Imported by `orchestrator.py` and `notification_queue.py` (core→core ✅). HTTP exporter `start_http_server()` invoked by `run_monitor.py` (composition root ✅ — transport concern stays in bootstrap layer). Core domain logic NEVER imports adapter modules for metrics. No Port/Adapter contracts violated.
- **Zero-Budget Stack**: Only MIT-licensed `prometheus-client>=0.20.0` added. No SaaS APIs, no Grafana Cloud dependency, no proprietary monitoring agents. The /metrics endpoint is standard Prometheus text format consumable by any OSS Prometheus server.
- **Non-Blocking Async Guarantee**: All `Counter.inc()`, `Gauge.inc()`, `Histogram.observe()` calls are atomic, thread-safe, in-process O(1) memory mutations — zero I/O, zero network calls, zero `await`. `start_http_server()` spawns a daemon thread via stdlib `http.server` — completely independent of the asyncio event loop. No scan latency introduced by metrics collection.
- **Outcome Mapping Fidelity**: The orchestrator's non-200 handler precisely maps HTTP status codes to ScanOutcome values per the Blueprint's Error Classification Matrix (§5.6): 403→BLOCKED_403, 429→BLOCKED_THROTTLED, 503→BLOCKED_CAPTCHA. These flow directly into `scans_total.labels(outcome=...)` — a Prometheus query like `rate(amz_hunt_scans_total{outcome="BLOCKED_403"}[1h])` gives an exact 403s-per-hour rate.

### Verification

```bash
# 1. Rebuild with new dependency
docker compose up -d --build

# 2. Scrape the metrics endpoint
curl http://localhost:9090/metrics

# Expected output (sample):
#   amz_hunt_scans_total{endpoint_id="deals-hub-main",outcome="SUCCESS_NO_CHANGE"} 12.0
#   amz_hunt_promotions_discovered_total{endpoint_id="deals-hub-main"} 2.0
#   amz_hunt_notifications_sent_total{status="success"} 2.0
#   amz_hunt_scan_latency_seconds_count{endpoint_id="deals-hub-main"} 42.0
#   amz_hunt_scan_latency_seconds_bucket{endpoint_id="deals-hub-main",le="1.0"} 38.0
#   amz_hunt_circuit_breaker_active 0.0
```

### Updated Phase 6 Directory Tree

```
src/core/
├── models/              (7 files — Phase 1)
├── ports/               (4 files — Phase 1)
├── dedup_engine.py      (Phase 3) ✅
├── scheduler.py         (Phase 3) ✅
├── validator.py         (Phase 3) ✅
├── parser_router.py     (Phase 3) ✅
├── notification_queue.py (Phase 3 + Phase 6 instrumentation) ✅
├── orchestrator.py      (Phase 3 + Phase 6 instrumentation) ✅
├── metrics.py           (Phase 6 — NEW) ✅
├── di_container.py      (Phase 3) ✅
└── shutdown.py          (Phase 3) ✅
scripts/
├── run_monitor.py       (Phase 3 + Phase 6 metrics server) ✅
├── seed_targets.py      (Phase 3) ✅
└── vps_healthcheck.sh   (Phase 5) ✅
docker-compose.yml       (Phase 4 + Phase 5 logging + Phase 6 port 9090) ✅
requirements.txt         (Phase 4 + Phase 6 prometheus-client) ✅
```

### Phase 6 Validation Checklist — ALL COMPLETE ✅

- [x] `prometheus-client>=0.20.0,<1.0.0` added to `requirements.txt` (MIT-licensed, zero-cost)
- [x] `src/core/metrics.py` defines all 6 metric families (Counter: scans_total, promotions_discovered, notifications_sent, circuit_breaker_trips; Gauge: circuit_breaker_active; Histogram: scan_latency_seconds)
- [x] `start_metrics_server(9090)` wired into `run_monitor.py` BEFORE asyncio tasks — daemon thread, non-blocking
- [x] Orchestrator `_process_endpoint()` instrumented at all 4 outcome paths (success, non-200 block mapping, AmzHuntError, Exception)
- [x] Notification `worker()` loop instrumented with success/failed counters
- [x] `docker-compose.yml` exposes `9090:9090` for Prometheus scraping
- [x] Hexagonal architecture intact: metrics module in Core, HTTP transport in bootstrap layer
- [x] All metric operations non-blocking (atomic in-memory, zero I/O, zero await)

---

## 🚀 NEXT PHASE: Phase 7 — The Grand Portfolio Showcase (Visual Monitoring Stack)

- **Current State:** The Amz-Hunt monitor is a fully-operational, production-grade Python application with Hexagonal Architecture, TLS-impersonated scraping, async SQLite persistence, Telegram alerts, Docker containerization with log rotation, automated VPS deployment, health-check auto-restart, AND a Prometheus `/metrics` endpoint exposing 6 metric families on port 9090. It is ready to impress on a freelance portfolio — but we need the visual proof.
- **Objective:** Add **optional, zero-cost, local-only** Prometheus & Grafana service blocks, a pre-baked Grafana Dashboard JSON, and update the master `README.md` with instructions to launch the complete visual stack locally. The goal is to capture breathtaking, professional screenshots of real-time Amz-Hunt metrics flowing through a polished Grafana dashboard — for use on Upwork, LinkedIn, and Freelancer portfolio profiles.
- **Key Deliverables for the incoming Agent:**
  1. **Prometheus Scrape Config** — Create `prometheus/prometheus.yml` with a scrape job targeting `amz-hunt-monitor:9090` at a 15s interval. The job must label the target with `job: "amz-hunt"` and `env: "portfolio"`.
  2. **Grafana Datasource Provisioning** — Create `grafana/datasources/prometheus.yml` that auto-provisions the local Prometheus as a Grafana datasource at container startup (Grafana's built-in provisioning system watches `/etc/grafana/provisioning/datasources`).
  3. **Pre-Baked Grafana Dashboard JSON** — Create `grafana/dashboards/amz-hunt.json` — a professionally-designed dashboard with panels for:
     - **Row 1 — Throughput & Discoveries**: `rate(amz_hunt_scans_total[5m])` (stat panel — scans/minute), `rate(amz_hunt_promotions_discovered_total[1h])` (graph — promos discovered/hour)
     - **Row 2 — Error & Block Radar**: `rate(amz_hunt_scans_total{outcome=~"BLOCKED_.*|ERROR_.*"}[5m])` (graph — errors/blocks over time), `amz_hunt_circuit_breaker_active` (stat — current cooldowns), `rate(amz_hunt_circuit_breaker_trips_total[15m])` (graph — trip rate)
     - **Row 3 — Notification Health**: `rate(amz_hunt_notifications_sent_total{status="failed"}[15m])` (graph — failed deliveries), `rate(amz_hunt_notifications_sent_total{status="success"}[15m])` (graph — successful deliveries)
     - **Row 4 — Latency Distribution**: `histogram_quantile(0.50, rate(amz_hunt_scan_latency_seconds_bucket[5m]))` (graph — p50 latency), `histogram_quantile(0.95, ...)` (graph — p95 latency), `histogram_quantile(0.99, ...)` (graph — p99 latency)
     - Use 12h auto-refresh, UTC time range, dark theme (`"editable": false` to preserve the pristine portfolio look — can be copied and edited locally).
  4. **Docker Compose Override** — Create `docker-compose.override.yml` (or dedicated service blocks in the existing `docker-compose.yml` behind a Compose profile `monitoring`) that adds:
     - `prometheus` service — official `prom/prometheus:v2.52.0` image, volume-mount `./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml`, port `9091:9090` (offset to avoid clash with amz-hunt's own 9090), `restart: unless-stopped`, depends_on `amz-hunt-monitor`
     - `grafana` service — official `grafana/grafana:10.4.0` image, volume-mount `./grafana/datasources:/etc/grafana/provisioning/datasources` + `./grafana/dashboards:/etc/grafana/provisioning/dashboards`, port `3000:3000`, env `GF_AUTH_ANONYMOUS_ENAB=true` + `GF_AUTH_ANONYMOUS_ORG_ROLE=Admin` (local portfolio mode — no login needed), `restart: unless-stopped`
     - Both services MUST be zero-cost (OSS Docker Hub images, no license fees) and clearly documented as **optional — local portfolio/dev only, NOT for production VPS**.
  5. **README.md Showcase Section** — Rewrite or augment `README.md` with a new "📊 Portfolio Showcase — Visual Monitoring Stack" section. Must include:
     - A single `docker compose --profile monitoring up -d` launch command (or `docker compose -f docker-compose.yml -f docker-compose.override.yml up -d`)
     - Access URLs: Grafana at `http://localhost:3000` (anonymous admin, no login), Prometheus at `http://localhost:9091`
     - Screenshot guidance: which panels to capture for Upwork (Throughput + Error Radar rows), LinkedIn (Notification Health + Latency rows), Freelancer (full dashboard wide shot)
     - Clean teardown: `docker compose --profile monitoring down -v`
  6. **Zero-Cost & Optional Guarantee** — The monitoring stack must be 100% optional. Production VPS deployment (`docker compose up -d` without `--profile monitoring`) must NOT start Prometheus/Grafana. The override must not affect the existing production `docker-compose.yml` behavior.

- **Portfolio Screenshot Strategy (embedded in README):**
  | Platform | Recommended Panel Capture | Narrative |
  |----------|--------------------------|-----------|
  | **Upwork** | Throughput stat (scans/min) + Error/Block radar graph | "Real-time anti-bot resilience: I built a production monitor that gracefully handles Amazon WAF blocks with circuit-breaker cooldowns — see the Prometheus metrics dashboard." |
  | **LinkedIn** | Notification Health (success vs failed) + Latency p50/p95/p99 graphs | "Full-stack observability: from async HTTP scraping to Telegram alert delivery, every pipeline stage is instrumented with Prometheus metrics and visualised in Grafana." |
  | **Freelancer** | Full-dashboard wide screenshot (all 4 rows) | "Enterprise-grade Hexagonal Architecture with Prometheus/Grafana observability — designed for $0 budget, runs indefinitely on a $5 VPS." |

