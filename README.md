# 🛒 Enterprise-Grade E-Commerce Promo Infrastructure (Amz-Hunt)

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![Architecture](https://img.shields.io/badge/Hexagonal_Architecture-FF4B4B?style=for-the-badge&logo=blueprint&logoColor=white)

> **Author:** Saeed Ali  
> **Role:** Backend & Software Architect  

## 📌 Executive Summary | ملخص تنفيذي
This repository contains the complete software architecture and data pipeline for a highly resilient, automated e-commerce monitoring system. Designed as a commercial-grade engine for Amazon Egypt, it bridges the gap between volatile web DOM structures and real-time event-driven notifications.

The system deliberately bypasses traditional scraping bottlenecks (such as IP bans and WAF blocks) by implementing a strict **Hexagonal Architecture (Separation of Concerns)**. By isolating the core business logic from external libraries, and offloading network evasion to a specialized TLS-spoofing adapter, the system achieves 24/7 high-speed telemetry, stealthy data extraction, and fault-tolerant alerting with zero infrastructure costs.

## 💼 Commercial Use Cases | حالات الاستخدام التجارية
This architecture is built with commercial scalability in mind, making it directly applicable to:
* **Affiliate Marketing Automation:** Instantaneous detection and broadcasting of flash sales to maximize referral conversions. *(أتمتة التسويق بالعمولة)*
* **Competitor Intelligence:** Real-time tracking of promotional strategies, hidden coupons, and pricing anomalies across thousands of endpoints. *(مراقبة المنافسين)*
* **Automated Procurement Pipelines:** Feeding high-confidence deal data into secondary automated purchasing systems before stock depletion. *(الشراء الآلي للعروض)*

## 🏗️ System Architecture | هيكلة النظام

The project is structured into fully decoupled functional layers:

### 1. The Core Engine (Domain Layer)
A completely isolated, dependency-free core containing immutable business rules and data models. 
* **Frozen Entities:** Uses strictly typed, immutable dataclasses (`ParsedCandidate`, `Promotion`) to guarantee state integrity.
* **Strict Interfaces (Ports):** Defines the exact contracts (Protocols) that any external database or HTTP client must satisfy, ensuring zero vendor lock-in.

### 2. The Anti-Detection Network Gateway (HTTP Adapter)
A specialized network layer designed to bypass Amazon's sophisticated Web Application Firewalls (WAF).
* **TLS Fingerprint Spoofing:** Utilizes `curl_cffi` to perfectly impersonate Chrome's JA3/JA4 cryptographic handshakes.
* **Dynamic Header Rotation:** Seamlessly rotates browser profiles, Sec-CH-UA hints, and localized Egyptian headers to appear as organic human traffic.

### 3. Dual-Phase Scraping Pipeline (Parsers)
* **HTML DOM Analyzer:** Evaluates 23 dynamic CSS selector patterns, walking up the DOM tree to extract deals with mathematical confidence scoring.
* **JSON API Hunter:** Recursively targets hidden AJAX endpoints, extracting structured promotional data before it even renders on the frontend.

### 4. Persistence & Alerting (Storage & Notifications)
* **Asynchronous SQLite (WAL Mode):** High-throughput, thread-safe local storage using `aiosqlite` with Write-Ahead Logging to prevent database locking during concurrent scans.
* **Resilient Telegram Integration:** Direct API communication featuring exponential backoff algorithms (250ms → 4s) to automatically recover from rate limits (HTTP 429).

## ⚙️ Engineering Highlights | تفاصيل هندسية
* **Strictly Non-Blocking Software:** Built entirely on `asyncio`. The system processes multiple API endpoints concurrently without ever halting the main execution thread.
* **Enterprise Error Boundaries:** All external library exceptions are caught and explicitly wrapped into domain-specific exceptions (e.g., `AmzHuntError`), preventing catastrophic runtime crashes.
* **Zero-Budget Constraint:** Engineered to deliver enterprise-grade performance and bypassing capabilities using only standard libraries and free/open-source tools ($0 operational cost).

## 🚀 Getting Started | التشغيل السريع

### Development Environment
* Developed and optimized for **Python 3.11+**.
* Fully verified decoupled architecture with strict `runtime_checkable` protocol compliance.

### Installation & Setup
1. **Clone the Repository:**
   ```bash
  git clone https://github.com/Eng-Saeed-Ali/Amz-Hunt.git
   cd Amz-Hunt
   ```
2. **Install the Adapters (Dependencies):**
   ```bash
   python -m pip install curl_cffi aiosqlite beautifulsoup4 lxml aiohttp
   ```
3. **Verify the Infrastructure:**
   Run the sanity check script to ensure all adapters successfully bind to the Core Domain ports.
   ```bash
   python temp_verify_phase2.py
   ```
   *Successful execution will yield: `✅ ALL SANITY CHECKS PASSED`*

---
*Building robust, anti-fragile software architectures from the core domain up.* ````
