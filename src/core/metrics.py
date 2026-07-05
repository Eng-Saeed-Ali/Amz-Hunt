"""Prometheus metrics definitions for the Amz-Hunt pipeline.

This module defines six metric families as specified in Phase 6 (Observability)
of the Agent Handoff. Metrics are defined as module-level singletons — import
them directly wherever instrumentation is needed.

Architecture Compliance (Hexagonal / Ports & Adapters):
  - This module lives in src/core/ because metrics are domain-level measurement
    instrumentation, analogous to logging. The prometheus_client library is a
    pure measurement/RPC-agnostic library (MIT-licensed, zero-cost), not an external
    service adapter.
  - Core services (orchestrator, notification_queue) import from here — a core→core
    relationship that respects the Dependency Inversion Principle.
  - The HTTP scraping endpoint (start_http_server) is started by the composition
    root (scripts/run_monitor.py), not by core domain logic — keeping the
    exporter transport concern in the entry-point/bootstrap layer.

Non-Blocking Guarantee:
  - All metric operations (Counter.inc, Gauge.set, Histogram.observe) are
    atomic, in-process, O(1) operations that mutate thread-safe shared memory
    structures. No I/O, no network calls, no await — zero async overhead.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ==========================================================================
# 1. amz_hunt_scans_total — Counter
# ==========================================================================
# Tracks every scan attempt (one per endpoint per poll cycle) with the
# outcome label describing the result. This is the primary throughput and
# error-rate metric.
#
# Labels:
#   endpoint_id : str   — TargetEndpoint.endpoint_id (e.g., "deals-hub-main")
#   outcome     : str   — ScanOutcome enum member name (SUCCESS_NEW_PROMO,
#                          SUCCESS_NO_CHANGE, BLOCKED_403, BLOCKED_CAPTCHA,
#                          BLOCKED_THROTTLED, ERROR_CONNECTION, ERROR_TIMEOUT,
#                          ERROR_PARSE, ERROR_UNKNOWN)
# ==========================================================================
scans_total = Counter(
    "amz_hunt_scans_total",
    "Total number of scan attempts (one per endpoint poll cycle)",
    labelnames=["endpoint_id", "outcome"],
)

# ==========================================================================
# 2. amz_hunt_promotions_discovered_total — Counter
# ==========================================================================
# Count of genuinely new (never-before-seen) promotions discovered.
# Incremented once per new Promotion after dedup passes.
#
# Labels:
#   endpoint_id : str   — Source endpoint that produced the discovery
# ==========================================================================
promotions_discovered_total = Counter(
    "amz_hunt_promotions_discovered_total",
    "Total number of new (never-before-seen) promotions discovered",
    labelnames=["endpoint_id"],
)

# ==========================================================================
# 3. amz_hunt_notifications_sent_total — Counter
# ==========================================================================
# Tracks notification delivery outcomes (Telegram or other channel).
# Incremented by the NotificationQueue worker after each delivery attempt.
#
# Labels:
#   status : str   — "success" or "failed"
# ==========================================================================
notifications_sent_total = Counter(
    "amz_hunt_notifications_sent_total",
    "Total number of notification delivery attempts",
    labelnames=["status"],
)

# ==========================================================================
# 4. amz_hunt_circuit_breaker_trips_total — Counter
# ==========================================================================
# Incremented each time an endpoint enters cooldown (circuit-breaker
# trips). Trips are triggered by block-worthy non-200 responses
# (403, 429, CAPTCHA) or consecutive failures reaching threshold.
#
# Labels:
#   endpoint_id : str   — The endpoint that tripped into cooldown
# ==========================================================================
circuit_breaker_trips_total = Counter(
    "amz_hunt_circuit_breaker_trips_total",
    "Total number of circuit-breaker trip events (endpoint enters cooldown)",
    labelnames=["endpoint_id"],
)

# ==========================================================================
# 5. amz_hunt_circuit_breaker_active — Gauge
# ==========================================================================
# Current number of endpoints in cooldown (circuit-breaker active).
# Set to 0 at startup; updated whenever endpoints enter/leave cooldown.
# Use set() to replace the value entirely, or inc()/dec() for delta updates.
# ==========================================================================
circuit_breaker_active = Gauge(
    "amz_hunt_circuit_breaker_active",
    "Current number of endpoints in circuit-breaker cooldown state",
)

# ==========================================================================
# 6. amz_hunt_scan_latency_seconds — Histogram
# ==========================================================================
# Distribution of HTTP request latencies (wall-clock fetch time).
# Observed only for successful HTTP fetches (status_code == 200).
#
# Labels:
#   endpoint_id : str   — The endpoint whose HTTP fetch was measured
#
# Buckets (seconds): 0.5, 1, 2.5, 5, 10, 30
#   - 0.5s: very fast (Amazon edge cache hit, small page)
#   - 1s:   typical healthy response
#   - 2.5s: slower but acceptable
#   - 5s:   borderline — potential network congestion
#   - 10s:  degraded — investigate
#   - 30s:  timeout threshold (max configured timeout)
# ==========================================================================
scan_latency_seconds = Histogram(
    "amz_hunt_scan_latency_seconds",
    "HTTP request latency distribution in seconds",
    labelnames=["endpoint_id"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)


# ==========================================================================
# Convenience helper: start the Prometheus HTTP scrape endpoint.
# ==========================================================================
# This is intentionally NOT called by core domain logic. It is invoked by
# the composition root (scripts/run_monitor.py) during bootstrap, after the
# DI container is assembled and before the asyncio event loop begins.
#
# start_http_server() spawns a daemon thread internally that serves /metrics
# via Python's stdlib http.server — no asyncio integration needed, and it
# coexists peacefully with the asyncio event loop.
# ==========================================================================

def start_metrics_server(port: int = 9090) -> None:
    """Start the Prometheus HTTP metrics endpoint on the given port.

    Spawns a lightweight daemon thread serving GET /metrics in Prometheus
    text exposition format. The thread is auto-cleaned on process exit.

    Args:
        port: TCP port to bind (default 9090, Prometheus convention).
    """
    start_http_server(port)