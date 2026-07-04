"""GracefulShutdown — signal-based shutdown coordination for the Amz-Hunt monitor.

Handles SIGINT (Ctrl+C) and SIGTERM (systemd/Docker stop) by setting an
asyncio.Event flag. The entry point awaits this event in parallel with the
orchestrator loop; when the flag is set, it cancels all running tasks and
closes resources (DB connection, HTTP sessions) cleanly.

Platform compatibility:
  - Unix (Linux/macOS): Uses loop.add_signal_handler (the asyncio-native way).
  - Windows: Falls back to signal.signal() (no add_signal_handler on win32).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Manages graceful shutdown via SIGINT/SIGTERM.

    Usage pattern (in run_monitor.py):

        shutdown = GracefulShutdown()
        shutdown.register_signals()
        orchestrator_task = asyncio.create_task(orchestrator.run_forever(endpoints))
        await shutdown.wait_for_shutdown()
        orchestrator_task.cancel()
        await asyncio.gather(orchestrator_task, return_exceptions=True)
        await storage.close()
    """

    def __init__(self) -> None:
        """Create a GracefulShutdown manager with an initially-unset Event."""
        self._shutdown_event = asyncio.Event()
        self._shutdown_requested = False

    @property
    def is_shutdown(self) -> bool:
        """Return True if shutdown has been requested (signal received)."""
        return self._shutdown_event.is_set()

    def register_signals(self) -> None:
        """Register SIGINT and SIGTERM handlers on the running event loop.

        On Unix: uses loop.add_signal_handler (asyncio-native, thread-safe).
        On Windows: falls back to signal.signal() (add_signal_handler is
        not available on win32 — see Python issue 36958).

        Must be called from within a running asyncio event loop (i.e., inside
        an async function after asyncio.run() or loop.run_until_complete()
        has started).
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop — signal handlers NOT registered")
            return

        if sys.platform == "win32":
            # Windows: add_signal_handler is not supported.
            # Use the older signal.signal() API which works but is less
            # integrated with the event loop. The handler simply sets the
            # event flag synchronously.
            def _win32_handler(signum: int, frame: object) -> None:
                logger.info("Received signal %d — initiating graceful shutdown", signum)
                self._shutdown_event.set()

            signal.signal(signal.SIGINT, _win32_handler)
            signal.signal(signal.SIGTERM, _win32_handler)
            logger.info("Signal handlers registered (Windows fallback mode)")
        else:
            # Unix: asyncio-native signal handling.
            # The handler runs in the event loop thread and is safe to
            # call loop-aware APIs.
            loop.add_signal_handler(
                signal.SIGINT,
                self._handle_signal,
                signal.SIGINT,
            )
            loop.add_signal_handler(
                signal.SIGTERM,
                self._handle_signal,
                signal.SIGTERM,
            )
            logger.info("Signal handlers registered (Unix asyncio mode)")

    def _handle_signal(self, signum: int) -> None:
        """Internal callback: set the shutdown event on signal reception.

        Args:
            signum: The signal number received (SIGINT=2 or SIGTERM=15).
        """
        signal_name = signal.Signals(signum).name
        logger.info("Received %s — initiating graceful shutdown", signal_name)
        self._shutdown_event.set()

    async def wait_for_shutdown(self) -> None:
        """Coroutine that blocks until a shutdown signal is received.

        Usage:
            await shutdown.wait_for_shutdown()
            # Signal received — now cancel tasks and clean up.
        """
        await self._shutdown_event.wait()
        logger.info("Shutdown event triggered — commencing graceful teardown")