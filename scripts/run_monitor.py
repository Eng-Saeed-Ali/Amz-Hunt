"""Entry point for the Amz-Hunt Amazon Egypt Promo Monitor.

Usage:
    python -m scripts.run_monitor

This is the single command to launch the full monitoring pipeline:
  1. Load configuration from .env
  2. Wire all adapters and core services via DIContainer
  3. Fetch active TargetEndpoints from the database
  4. Start the NotificationQueue worker as a background task
  5. Run the ScanOrchestrator in an infinite polling loop
  6. Handle graceful shutdown (SIGINT/SIGTERM → clean teardown)
"""

from __future__ import annotations

import asyncio
import logging

from src.config.settings import settings
from src.core.di_container import DIContainer
from src.core.shutdown import GracefulShutdown

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Set up standard library logging based on settings.LOG_LEVEL.

    Format:  [YYYY-MM-DD HH:MM:SS] [LEVEL] [module] message
    This provides structured, timestamped logs suitable for both
    development debugging and production monitoring (Docker logs,
    systemd journal, etc.).
    """
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Silence noisy third-party loggers at INFO level
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("curl_cffi").setLevel(logging.WARNING)
    logging.getLogger("bs4").setLevel(logging.WARNING)


async def main() -> None:
    """Application entry point — build, wire, run, and shut down gracefully.

    Lifecycle:
        1. Configure logging
        2. Build the DI container (adapters + core services)
        3. Fetch TargetEndpoints from the database
        4. Start NotificationQueue.worker() as a background asyncio task
        5. Launch orchestrator.run_forever(endpoints) as a background task
        6. Wait for SIGINT/SIGTERM via GracefulShutdown
        7. Cancel orchestrator + worker tasks, close DB connection
    """
    _configure_logging()
    logger.info("=== Amz-Hunt Monitor Starting ===")
    logger.info("Log level: %s | DB path: %s", settings.LOG_LEVEL, settings.DB_PATH)

    # ── 1. Build the full object graph ────────────────────────────────
    container = DIContainer()
    orchestrator = await container.build()
    logger.info("DI container built — all adapters wired")

    # ── 2. Fetch active polling targets ───────────────────────────────
    endpoints = await container.storage.get_active_targets()
    if not endpoints:
        logger.warning(
            "No active TargetEndpoints found in the database. "
            "Run 'python -m scripts.seed_targets' to seed default targets, "
            "then restart the monitor."
        )
        await container.storage.close()
        return

    logger.info("Loaded %d active TargetEndpoint(s)", len(endpoints))
    for ep in endpoints:
        logger.info(
            "  • %s [%s] → %s (interval: %ds)",
            ep.endpoint_id,
            ep.parser_type,
            ep.url,
            ep.poll_interval_seconds,
        )

    # ── 3. Start NotificationQueue worker as background task ──────────
    worker_task = asyncio.create_task(
        container.queue.worker(),
        name="notification_worker",
    )
    logger.info("Notification worker started")

    # ── 4. Set up graceful shutdown ───────────────────────────────────
    shutdown = GracefulShutdown()
    shutdown.register_signals()

    # ── 5. Launch orchestrator polling loop ───────────────────────────
    orchestrator_task = asyncio.create_task(
        orchestrator.run_forever(endpoints),
        name="orchestrator_loop",
    )
    logger.info("Orchestrator polling loop started — monitoring %d endpoints", len(endpoints))

    # ── 6. Wait for shutdown signal ───────────────────────────────────
    await shutdown.wait_for_shutdown()

    # ── 7. Graceful teardown ──────────────────────────────────────────
    logger.info("Shutdown signal received — cancelling tasks...")
    orchestrator_task.cancel()
    worker_task.cancel()

    # Wait for tasks to acknowledge cancellation (with a grace period)
    done, pending = await asyncio.wait(
        [orchestrator_task, worker_task],
        timeout=10.0,  # 10-second grace period for in-flight work
    )
    if pending:
        logger.warning(
            "%d task(s) did not finish within grace period — forcing exit",
            len(pending),
        )
        for task in pending:
            task.cancel()

    # Collect any exceptions from cancelled tasks (CancelledError is expected)
    for task in done:
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # Expected — task was cancelled cleanly
        except Exception:
            logger.exception("Task raised unexpected exception during teardown")

    # Close the database connection
    await container.storage.close()
    logger.info("Database connection closed")

    logger.info("=== Amz-Hunt Monitor Shutdown Complete ===")


if __name__ == "__main__":
    asyncio.run(main())