# Agent_Handoff.md — Phase 1 Completion → Phase 2 Bridge

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
│   │   │   ├── curl_cffi_client.py  (PLACEHOLDER — Phase 2)
│   │   │   └── header_pool.py       (PLACEHOLDER — Phase 2)
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── sqlite_backend.py    (PLACEHOLDER — Phase 2)
│   │   │   └── migrations.py        (PLACEHOLDER — Phase 2)
│   │   ├── notification/
│   │   │   ├── __init__.py
│   │   │   └── telegram_bot.py      (PLACEHOLDER — Phase 2)
│   │   └── parsers/
│   │       ├── __init__.py
│   │       ├── html_dom_parser.py    (PLACEHOLDER — Phase 2)
│   │       └── json_endpoint_parser.py (PLACEHOLDER — Phase 2)
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

## - [ ] Architectural Notes for the Next Agent

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

10. **The orchestrator's global error boundary catches `AmzHuntError`** only. Any adapter that raises a non-`AmzHuntError` exception will crash the polling loop. This is a hard contract.

---

## - [ ] Next Steps for Phase 2: Building the Concrete Adapters

### Priority Order (build in this sequence):

#### 1. `src/adapters/storage/sqlite_backend.py` — HIGHEST PRIORITY
Implement `IStorageBackend` using `aiosqlite`. This is the first adapter because:
- The `migrations.py` schema must be designed first (next to this file)
- Every other adapter needs the storage backend for its integration tests
- Must be async-safe for concurrent asyncio tasks

**Key implementation notes:**
- Use `aiosqlite` (NOT synchronous `sqlite3`) — all methods must be `async`
- Schema: promotions table with UNIQUE constraint on `content_fingerprint`, target_endpoints table, scan_log table (append-only), and a migration version tracker
- `upsert_promotion()` returns `True` on INSERT, `False` on UPDATE (use `INSERT OR IGNORE` + check `rowcount`)
- `record_failure()` increments `consecutive_failures` in SQL (`UPDATE ... SET consecutive_failures = consecutive_failures + 1`) and returns the new value
- `log_scan()` serializes `ScanResult` fields into scan_log columns — the `ScanOutcome` enum should be stored as its `.name` string

#### 2. `src/adapters/http/curl_cffi_client.py` — HIGH PRIORITY
Implement `IHttpClient` using `curl_cffi.requests.AsyncSession`.

**Key implementation notes:**
- Use `curl_cffi.requests` (NOT `curl_cffi.asyncio` — the Blueprint specifies the requests API)
- Maintain a `dict[str, AsyncSession]` pool keyed by impersonate profile — reuse sessions for connection pooling
- `fetch()` must catch ALL network exceptions and wrap them in `HttpClientError` (from `src.core.models.exceptions`)
- HTTP-level errors (4xx, 5xx, CAPTCHA pages) are NOT exceptions — they are recorded in the `HttpResponse.status_code` and `HttpResponse.body`
- `rotate_fingerprint()` cycles through a configurable ordered list: `["chrome124", "chrome120", "firefox120", "safari17_0", "edge101"]`
- `session_metrics()` is synchronous — aggregate counts from the session pool

#### 3. `src/adapters/http/header_pool.py`
Build a header rotation utility that provides browser-realistic `User-Agent`, `Accept-Language`, `Sec-Ch-Ua`, and other Client Hints headers. The `curl_cffi_client` will consume this pool.

#### 4. `src/adapters/parsers/html_dom_parser.py` + `src/adapters/parsers/json_endpoint_parser.py`
Implement `IParser` for both parser types.

**HTML DOM Parser:**
- `parser_type` property returns `"html_dom"`
- Uses `BeautifulSoup4` with `lxml` parser (NOT `html.parser` — lxml is faster and more tolerant of Amazon's messy HTML)
- Extract promo candidates by CSS selector matching (cards, data-promo-id attributes, deal widgets)
- Assign `confidence_score` based on selector specificity: exact `data-promo-id` match = 1.0, fuzzy title match = 0.5–0.7

**JSON Endpoint Parser:**
- `parser_type` property returns `"json_endpoint"`
- Parses Amazon AJAX/JSON responses that contain structured promo data
- Extract from known Amazon JSON response shapes (e.g., `response.deals[]`, `response.promotions[]`)

**Critical:** Return `[]` (empty list) if nothing found — never `None`.

#### 5. `src/adapters/notification/telegram_bot.py`
Implement `INotificationService` using `aiogram` or raw `aiohttp` against Telegram Bot API.

**Key implementation notes:**
- Retry with exponential backoff: 250ms → 500ms → 1s → 2s → fail (max 4 retries)
- `send_promo_alert()` formats promotion as: title, URL, timestamp, source endpoint hint
- `send_health_check()` and `send_error_alert()` format structured Telegram messages
- Severity levels: "info" = ℹ️, "warning" = ⚠️, "critical" = 🚨

### Phase 2 Validation Checklist

Before handing off to Phase 3, the Phase 2 agent MUST verify:
- [ ] `sqlite_backend.py` passes `isinstance(sqlite_backend, IStorageBackend)` (runtime_checkable)
- [ ] `curl_cffi_client.py` successfully fetches `https://www.amazon.eg/` with status 200
- [ ] `html_dom_parser.py` extracts at least one `ParsedCandidate` from a known Amazon deals page
- [ ] `telegram_bot.py` sends a test message to a configurable chat ID
- [ ] All adapter errors inherit from the correct `AmzHuntError` subclass
- [ ] SQLite database file is created at `data/amz_hunt.db` (configurable path)

### Files NOT to touch in Phase 2

- `src/core/**` — All core models and ports are complete and frozen for Phase 1
- `Architecture_Blueprint.md` — Source of truth, reference only
- `src/core/orchestrator.py` — This is Phase 3 territory

---

*Generated by Phase 1 Foundation Agent — ready for Phase 2 Adapter Implementation.*