# 🛒 Enterprise-Grade E-Commerce Promo Infrastructure (Amz-Hunt)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite_WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram_Bot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![Architecture](https://img.shields.io/badge/Hexagonal_Architecture-FF4B4B?style=for-the-badge&logo=blueprint&logoColor=white)

> **Author:** Eng-Saeed-Ali  
> **Role:** Backend & Software Architect  
> **Status:** Production-Ready (Golden Master) 🚀

---

## 📌 Executive Summary | ملخص تنفيذي

This repository contains the complete software architecture and data pipeline for a highly resilient, automated e-commerce monitoring system. Designed as a commercial-grade engine for Amazon Egypt, it bridges the gap between volatile web DOM structures and real-time event-driven notifications.

The system deliberately bypasses traditional scraping bottlenecks (such as IP bans and WAF blocks) by implementing a strict **Hexagonal Architecture (Separation of Concerns)**. By isolating the core business logic from external libraries, and offloading network evasion to a specialized TLS-spoofing adapter, the system achieves 24/7 high-speed telemetry, stealthy data extraction, and fault-tolerant alerting with **zero infrastructure costs ($0)**.

---

## ✨ Core Features | المميزات الأساسية

* **Zero-Budget Anti-Bot Shield:** Utilizes `curl_cffi` to spoof Chrome TLS fingerprints (e.g., chrome124) to bypass Amazon's anti-bot protections seamlessly.
* **Smart Deduplication Engine:** Two-layer deduplication (SHA-256 content fingerprinting + Promo IDs) to ensure zero duplicate notifications.
* **Intelligent Scheduler:** Active-hours polling with decorrelated Jitter (randomized delays) to mimic human behavior and avoid predictable rate-limiting.
* **Resilient Notification Queue:** Asynchronous Telegram delivery with Exponential Backoff and guaranteed queue consumption to prevent deadlocks.
* **Platform-Aware Graceful Shutdown:** Captures `SIGINT/SIGTERM` to safely drain queues and close DB connections (Unix & Windows compatible).

---

## ⚙️ Engineering Highlights | تفاصيل هندسية

* **Strict Hexagonal Architecture:** `Dependency Injection (DI Container)` is the *only* composition root. The Core domain is completely agnostic of the Web, Database, or Notification mechanisms.
* **Strictly Non-Blocking Software:** Built entirely on `asyncio`. The system processes multiple API endpoints concurrently without ever halting the main execution thread.
* **Enterprise Error Boundaries:** All external library exceptions are caught and explicitly mapped into domain-specific exceptions (e.g., `AmzHuntError`, `HttpClientError`, `ParserError`).
* **Defensive Pipeline Guards:** Pre-emptive HTTP Status Code guards protect the DOM parsers from crashing on 403/500 responses.

---

## 🚀 Getting Started | التشغيل السريع

### 1️⃣ Clone the Repository & Install Dependencies
Developed and optimized for **Python 3.11+**. Run the following commands in your terminal to clone and setup dependencies:

```bash
git clone [https://github.com/Eng-Saeed-Ali/Amz-Hunt.git](https://github.com/Eng-Saeed-Ali/Amz-Hunt.git)
cd Amz-Hunt
pip install curl_cffi aiosqlite beautifulsoup4 lxml aiohttp pydantic-settings
```

### 2️⃣ Environment Configuration
Create your environment file to store secrets securely (it is ignored by Git automatically):

```bash
cp .env.example .env
```

### 3️⃣ Seed the Database (Idempotent Setup)
Initialize the SQLite database and insert the default Amazon Egypt targets into the database securely without causing any conflicts or data duplication:

```bash
python -m scripts.seed_targets
```

### 4️⃣ Launch the Monitor
Start the main orchestrator engine along with background notification workers:

```bash
python -m scripts.run_monitor
```

---

## 📁 Directory Structure (Ports & Adapters)

This clean directory tree maps out how the Hexagonal Architecture pattern isolates our Core application from outside dependencies:

```text
src/
├── core/                   # The Core Domain (Zero external dependencies)
│   ├── models/             # Frozen Dataclasses (Promotion, TargetEndpoint)
│   ├── ports/              # Interfaces (IStorageBackend, IHttpClient)
│   ├── dedup_engine.py     # Content fingerprinting logic
│   ├── scheduler.py        # Jitter & active hours logic
│   ├── validator.py        # Text & keyword filter logic
│   ├── parser_router.py    # Multi-parser dispatcher
│   ├── notification_queue.py # Async queue with backoff
│   ├── orchestrator.py     # The Master Pipeline execution loop
│   └── di_container.py     # Dependency Injection / Composition Root
├── adapters/               # The Outside World (Infrastructure integration)
│   ├── storage/            # SQLite with WAL mode implementation
│   ├── http/               # curl_cffi with Header Rotation implementation
│   ├── parsers/            # BeautifulSoup4 DOM & JSON extractors
│   └── notification/       # Telegram Bot API implementation
├── config/
│   └── settings.py         # Pydantic Env Loader (loads secrets securely)
└── scripts/                # Execution Entry Points
    ├── seed_targets.py     # Database seeder script
    └── run_monitor.py      # Main system execution script
```

---
*Building robust, anti-fragile backend systems.*