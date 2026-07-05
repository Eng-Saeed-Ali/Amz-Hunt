<!--
  ╔══════════════════════════════════════════════════════════════╗
  ║                    🏹  AMZ-HUNT  🏹                          ║
  ║        Amazon Egypt Promotion Monitor & Alert System         ║
  ╚══════════════════════════════════════════════════════════════╝
-->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)">
    <img alt="Amz-Hunt" width="480" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0ODAiIGhlaWdodD0iMTIwIiB2aWV3Qm94PSIwIDAgNDgwIDEyMCI+PGRlZnM+PGZpbHRlciBpZD0iZ3ciPjxmZURyb3BTaGFkb3cgZHg9IjIiIGR5PSIyIiBzdGREZXZpYXRpb249IjMiIGZsb29kLW9wYWNpdHk9IjAuMyIvPjwvZmlsdGVyPjwvZGVmcz48cmVjdCB3aWR0aD0iNDgwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iIzBkMTExNyIgcng9IjE0Ii8+PHRleHQgeD0iMjQwIiB5PSI3MCIgZm9udC1mYW1pbHk9Im1vbm9zcGFjZSIgZm9udC1zaXplPSI0MiIgZmlsbD0iIzAwZmY0MSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsdGVyPSJ1cmwoI2d3KSIgZm9udC13ZWlnaHQ9ImJvbGQiPsOxIE1aLUhVTlQ8L3RleHQ+PHRleHQgeD0iMjQwIiB5PSIxMDAiIGZvbnQtZmFtaWx5PSJtb25vc3BhY2UiIGZvbnQtc2l6ZT0iMTYiIGZpbGw9IiM3M2E3NzMiIHRleHQtYW5jaG9yPSJtaWRkbGUiPkFtYXpvbiBFZ3lwdCBQcm9tbyBNb25pdG9yPC90ZXh0Pjwvc3ZnPg==">
  </picture>
</p>

<p align="center">
  <strong>Zero-Budget • Zero-API • TLS-Impersonated</strong><br>
  <em>Detect Amazon Egypt deals before they expire — no Amazon PA-API key needed.</em>
</p>

<p align="center">
  <!-- Badges -->
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white" alt="Docker Ready">
  <img src="https://img.shields.io/badge/architecture-hexagonal-7B68EE.svg" alt="Hexagonal Architecture">
  <img src="https://img.shields.io/badge/phase-4%2F7%20complete-00d4aa.svg" alt="Phase 4/7 Complete">
</p>

---

## 📋 Table of Contents

- [⚡ Quick Start](#-quick-start)
- [🎯 What Is Amz-Hunt?](#-what-is-amz-hunt)
- [🏗 Architecture](#-architecture)
- [🔧 Tech Stack & Dependencies](#-tech-stack--dependencies)
- [📂 Project Structure](#-project-structure)
- [⚙ Configuration](#-configuration)
- [📊 Database Schema](#-database-schema)
- [🚀 Running the Monitor](#-running-the-monitor)
- [🐳 Docker Deployment](#-docker-deployment)
- [📡 Monitoring & Debugging](#-monitoring--debugging)
- [🤝 Contributing](#-contributing)
- [📈 Roadmap](#-roadmap)
- [📄 License](#-license)

---

## ⚡ Quick Start

```bash
# 1. Clone & enter
git clone https://github.com/Eng-Saeed-Ali/Amz-Hunt.git
cd Amz-Hunt

# 2. Set up environment
cp .env.example .env
# Edit .env → add your TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID

# 3. Install & seed
pip install -r requirements.txt
python -m scripts.seed_targets

# 4. Launch
python -m scripts.run_monitor
```

> **Docker users:** `docker compose up -d` after step 2. See [🐳 Docker Deployment](#-docker-deployment).

---

## 🎯 What Is Amz-Hunt?

**Amz-Hunt** monitors Amazon Egypt (`amazon.eg`) deal pages in near-real-time, detects new promotions the instant they appear, and pushes instant Telegram alerts — *without* the official Product Advertising API (which requires 3+ qualifying sales before granting access).

| Challenge | Amz-Hunt's Solution |
|-----------|---------------------|
| No PA-API access (pre-sale chicken-and-egg) | Direct HTML scraping + AJAX JSON endpoints |
| Amazon WAF blocks scripted HTTP clients | TLS fingerprint impersonation (`curl_cffi`) as Chrome 124 |
| Zero budget for infrastructure | SQLite (WAL mode) + single Docker container, $0/month |
| Arabic + English mixed content | Parser handles bidirectional text, deals detected regardless of language |

---

## 🏗 Architecture

Amz-Hunt implements **Hexagonal (Ports & Adapters)** architecture. The core domain (`src/core/`) has zero knowledge of HTTP, SQL, or Telegram — it depends only on abstract Protocols (`IHttpClient`, `IStorageBackend`, `INotificationService`). Adapters (`src/adapters/`) implement those protocols with concrete technology choices.

```
┌─────────────────────────────────────────────────────────┐
│                    ENTRY POINTS                          │
│  scripts/run_monitor.py   scripts/seed_targets.py        │
└──────────┬──────────────────────────┬────────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────────────────────────────────────────────┐
│                  DI CONTAINER                             │
│  src/core/di_container.py                                │
│  Assembles: SQLiteBackend, CurlCffiClient,               │
│  TelegramNotifier → ScanOrchestrator                     │
└──────────┬──────────────────────────┬────────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│    ADAPTERS (src/)   │    │      CORE DOMAIN (src/core/)  │
│                      │    │                              │
│  adapters/storage/   │◄───│  ports/storage.py            │
│  → SQLiteBackend     │    │  (IStorageBackend Protocol)  │
│                      │    │                              │
│  adapters/http/      │◄───│  ports/http_client.py        │
│  → CurlCffiClient    │    │  (IHttpClient Protocol)      │
│                      │    │                              │
│  adapters/notifier/  │◄───│  ports/notification.py       │
│  → TelegramNotifier  │    │  (INotificationService)      │
│                      │    │                              │
└──────────────────────┘    │  ScanOrchestrator             │
                            │  (7-phase pipeline)           │
                            │  Scheduler → Fetch → Parse    │
                            │  → Validate → Dedup →        │
                            │  Notify → Log                 │
                            └──────────────────────────────┘
```

### Pipeline Phases (Current Completion: Phases 1–4 ✅)

| Phase | Status | What It Delivers |
|-------|--------|------------------|
| **Phase 1** — Foundation | ✅ Complete | Settings, models, DB schema, project scaffold |
| **Phase 2** — Full Wiring | ✅ Complete | DI container, all adapters wired, orchestrator 7-phase pipeline |
| **Phase 3** — Intelligence | ✅ Complete | Dedup engine, keyword validation, anti-bot jitter, graceful shutdown |
| **Phase 4** — Containerization | ✅ Complete | Multi-stage Dockerfile, docker-compose, non-root user, healthcheck |
| **Phase 5** — Retry & Resilience | 🔲 Planned | Exponential backoff, circuit breaker, broken-link auto-detection |
| **Phase 6** — Observability | 🔲 Planned | Prometheus metrics, Grafana dashboard, scan statistics API |
| **Phase 7** — Marketplace | 🔲 Planned | Multi-domain support (KSA, UAE), product-specific tracking |

---

## 🔧 Tech Stack & Dependencies

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `curl_cffi` | `>=0.7.0,<1.0.0` | TLS fingerprint impersonation (Chrome 124) — bypasses Amazon WAF | MIT |
| `aiosqlite` | `>=0.20.0,<1.0.0` | Async SQLite with WAL mode — non-blocking DB access | MIT |
| `beautifulsoup4` | `>=4.12.0,<5.0.0` | HTML parsing & DOM traversal | MIT |
| `lxml` | `>=5.0.0,<6.0.0` | Fast C-backed XML/HTML parser (BS4 backend) | BSD |
| `pydantic-settings` | `>=2.0.0,<3.0.0` | Type-safe .env configuration management | MIT |
| `aiohttp` | `>=3.9.0,<4.0.0` | Async HTTP for Telegram Bot API calls | Apache 2.0 |

> **All dependencies are MIT or Apache 2.0 licensed** — zero cost, zero copyleft restrictions.

---

## 📂 Project Structure

```
Amz-Hunt/
├── src/
│   ├── core/                    # Hexagonal core (zero adapter imports)
│   │   ├── models/              # Dataclasses: Promotion, ScanResult, TargetEndpoint
│   │   ├── ports/               # Abstract Protocols: IHttpClient, IStorageBackend, INotificationService
│   │   ├── di_container.py      # Dependency injection — wires adapters → orchestrator
│   │   ├── orchestrator.py      # 7-phase scan pipeline (the "brain")
│   │   ├── dedup_engine.py      # Fingerprint-based duplicate detection
│   │   ├── parser_router.py     # Dispatches HTML DOM vs JSON endpoint parsers
│   │   ├── scheduler.py         # Active-hours gate + interval scheduling
│   │   ├── validator.py         # Keyword + confidence validation
│   │   ├── notification_queue.py# Async producer-consumer queue for Telegram alerts
│   │   └── shutdown.py          # SIGINT/SIGTERM graceful teardown (Unix + Windows)
│   │
│   ├── adapters/                # Hexagonal adapters (implement Protocols)
│   │   ├── storage/
│   │   │   ├── sqlite_backend.py # IStorageBackend → aiosqlite
│   │   │   └── migrations.py    # Schema DDL (idempotent)
│   │   ├── http/
│   │   │   ├── curl_cffi_client.py # IHttpClient → curl_cffi (TLS impersonated)
│   │   │   └── parsers/         # HTML DOM parser + JSON endpoint parser
│   │   └── notifier/
│   │       └── telegram_notifier.py # INotificationService → Telegram Bot API
│   │
│   ├── config/
│   │   └── settings.py          # pydantic-settings from .env
│   │
│   └── utils/                   # Utility functions
│
├── scripts/
│   ├── run_monitor.py           # 🚀 Main entry point — launch the monitor
│   ├── seed_targets.py          # 🌱 Seed default Amazon EG endpoints (idempotent)
│   └── debug_dump_html.py       # 🔧 Fetch & save raw HTML for CSS selector analysis
│
├── tests/
│   ├── unit/                    # Unit tests (pytest)
│   └── integration/             # Integration tests
│
├── data/                        # SQLite DB storage (bind-mounted in Docker)
├── Dockerfile                   # Multi-stage build → slim production image
├── docker-compose.yml           # One-command deployment
├── .env.example                 # Environment variable template
├── requirements.txt             # Pinned runtime dependencies
├── Agent_Handoff.md             # AI agent continuity document
├── Architecture_Blueprint.md    # Full system design specification (private planning doc)
└── README.md                    # ← You are here
```

---

## ⚙ Configuration

All configuration lives in `.env` (never committed). Copy `.env.example` and fill in your values:

```bash
# .env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghijk   # From @BotFather
TELEGRAM_CHAT_ID=-1001234567890               # Your channel/group ID
DB_PATH=data/amz_hunt.db                      # Default — can change for testing
LOG_LEVEL=INFO                                 # DEBUG | INFO | WARNING | ERROR
DEFAULT_IMPERSONATE_PROFILE=chrome124          # TLS fingerprint to impersonate
```

The `Settings` class in `src/config/settings.py` loads these via `pydantic-settings` with type validation.

---

## 📊 Database Schema

Two main tables in SQLite (WAL mode):

**`target_endpoints`** — Configurable polling targets
| Column | Description |
|--------|-------------|
| `endpoint_id` | Unique slug (e.g., `amz-eg-deals-page`) |
| `url` | Full Amazon EG URL to poll |
| `parser_type` | `html_dom` or `json_endpoint` |
| `poll_interval_seconds` | Minimum seconds between polls |
| `active_hours_start/end` | UTC hour range for active polling |
| `impersonate_profile` | TLS fingerprint profile for `curl_cffi` |
| `enabled` | 0=disabled, 1=active |
| `consecutive_failures` | Cooldown escalation counter |
| `circuit_breaker_until_utc` | Timestamp when cooldown expires |

**`promotions`** — Detected deals
| Column | Description |
|--------|-------------|
| `promo_id` | Amazon's internal promotion ID |
| `url` | Direct deal landing page |
| `content_fingerprint` | SHA256 of normalized promo content (dedup UNIQUE constraint) |
| `first_seen_utc` | Unix timestamp of first discovery |
| `alert_sent` | 0=pending notification, 1=alert delivered |

**`scan_log`** — Append-only telemetry (every poll attempt logged)

---

## 🚀 Running the Monitor

### Local (Python)

```bash
pip install -r requirements.txt
python -m scripts.seed_targets    # First time only (idempotent — safe to re-run)
python -m scripts.run_monitor     # Starts infinite polling loop
```

The monitor runs forever until `Ctrl+C` (SIGINT) or `docker stop` (SIGTERM). Graceful shutdown cancels in-flight tasks and closes the DB connection cleanly.

### What You'll See

```
[2026-07-05 10:00:01] [INFO    ] [scripts.run_monitor] === Amz-Hunt Monitor Starting ===
[2026-07-05 10:00:01] [INFO    ] [scripts.run_monitor] Log level: INFO | DB path: data/amz_hunt.db
[2026-07-05 10:00:02] [INFO    ] [scripts.run_monitor] DI container built — all adapters wired
[2026-07-05 10:00:02] [INFO    ] [scripts.run_monitor] Loaded 1 active TargetEndpoint(s)
[2026-07-05 10:00:02] [INFO    ] [scripts.run_monitor]   • amz-eg-deals-page [html_dom] → ...deals (interval: 300s)
[2026-07-05 10:00:02] [INFO    ] [scripts.run_monitor] Notification worker started
[2026-07-05 10:00:02] [INFO    ] [scripts.run_monitor] Orchestrator polling loop started — monitoring 1 endpoints
[2026-07-05 10:00:02] [INFO    ] [src.core.orchestrator] Scanning endpoint: amz-eg-deals-page → ...deals
[2026-07-05 10:00:04] [INFO    ] [src.core.orchestrator] HTTP 200 | 48562 bytes | 2103ms | TLS=chrome124
[2026-07-05 10:00:05] [INFO    ] [src.core.orchestrator] Parsed 14 candidate(s) from amz-eg-deals-page
[2026-07-05 10:00:05] [INFO    ] [src.core.orchestrator] Validate + Dedup: 3 passed, 11 rejected → 3 NEW promotion(s)
[2026-07-05 10:00:05] [INFO    ] [src.core.orchestrator] Scan complete for amz-eg-deals-page: SUCCESS_NEW_PROMO
[2026-07-05 10:00:05] [INFO    ] [src.core.orchestrator] Next scan in ~52s (cycle 0, 1 endpoint(s))
```

---

## 🐳 Docker Deployment

```bash
# Build & start in detached mode
docker compose up -d --build

# View logs
docker compose logs -f amz-hunt

# Check resource usage
docker stats amz-hunt

# Stop gracefully (SIGTERM → clean shutdown)
docker compose down
```

**What the Docker setup provides:**
- Multi-stage build: `uv`-based dependency resolution → slim final image (~180 MB)
- Non-root `appuser` (UID 1000) for security
- `HEALTHCHECK` via `pgrep -f run_monitor` every 60s
- `restart: unless-stopped` — survives host reboots
- Memory limit: 128 MB (configurable in `docker-compose.yml`)
- `./data` bind-mounted for persistent SQLite storage
- `.env` file passed through to container for Telegram credentials

---

## 📡 Monitoring & Debugging

| Task | Command |
|------|---------|
| View live logs | `docker compose logs -f amz-hunt` |
| Container resource usage | `docker stats amz-hunt` |
| Shell into container | `docker compose exec amz-hunt /bin/sh` |
| Dump HTML for parser debugging | `python -m scripts.debug_dump_html` |
| Re-seed targets (update URLs/config) | `python -m scripts.seed_targets` |
| Check scan statistics | Query SQLite: `sqlite3 data/amz_hunt.db "SELECT outcome, COUNT(*) FROM scan_log GROUP BY outcome"` |

---

## 🤝 Contributing

Contributions are welcome! Amz-Hunt is designed as a portfolio piece and open-source tool.

1. **Fork** the repository
2. **Create a feature branch** (`git checkout -b feat/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push** to your fork (`git push origin feat/amazing-feature`)
5. Open a **Pull Request** against `main`

> Please ensure your code follows the existing Hexagonal architecture pattern — adapters implement Protocols, core never imports adapter code. Run `python -m scripts.seed_targets && python -m scripts.run_monitor` to confirm nothing is broken before submitting.

**Areas where contributions would be especially valuable:**
- New parsers for additional Amazon domains (KSA: `amazon.sa`, UAE: `amazon.ae`)
- Prometheus metrics exporter
- Web dashboard for scan statistics
- Additional notification channels (Discord, Slack, Email)

---

## 📈 Roadmap

| Phase | Goal | Status |
|-------|------|--------|
| **Phase 1** | Foundation — Settings, models, DB schema | ✅ Complete |
| **Phase 2** | Full Wiring — DI container, all adapters, 7-phase pipeline | ✅ Complete |
| **Phase 3** | Intelligence — Dedup, validation, jitter, graceful shutdown | ✅ Complete |
| **Phase 4** | Containerization — Dockerfile, compose, healthcheck | ✅ Complete |
| **Phase 5** | Resilience — Exponential backoff, circuit breaker, broken-link detection | 🔲 Next |
| **Phase 6** | Observability — Prometheus metrics, Grafana, stats API | 🔲 Planned |
| **Phase 7** | Marketplace — Multi-domain (KSA, UAE), product-specific watchlists | 🔲 Planned |

---

## 📄 License

MIT © [Saeed Ali](https://github.com/Eng-Saeed-Ali)

See [LICENSE](LICENSE) for full text.

---

<p align="center">
  <sub>Built with ❤️ in Cairo • Zero budget, maximum ingenuity</sub>
</p>