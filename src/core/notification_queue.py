"""NotificationQueue — async worker that delivers Promotions to the notification channel."""

from __future__ import annotations

import asyncio
import logging

from src.core.models.exceptions import NotificationError
from src.core.models.promotion import Promotion
from src.core.ports.notification import INotificationService

logger = logging.getLogger(__name__)


class NotificationQueue:
    """Decoupled async notification consumer backed by an asyncio.Queue.

    The ScanOrchestrator enqueues discovered Promotions here, then a background
    asyncio task (the worker loop) dequeues and delivers them one-by-one to the
    INotificationService adapter. This decoupling ensures that notification
    latency or transient failures (Telegram API 429, network hiccups) never block
    the main scan pipeline.

    Per Architecture Blueprint Section 3.4, this is the "notify" sink at the
    tail of the Orchestrator pipeline. Retry-with-backoff for notification
    delivery is owned by the adapter (TelegramBotService); this queue provides
    resilience against worker crashes via a broad try/except.

    Lifecycle:
        - enqueue() is called from the orchestrator coroutine.
        - worker() runs as a long-lived asyncio task, started by the orchestrator
          or supervisor, and cancelled on graceful shutdown.
    """

    def __init__(self, notifier: INotificationService) -> None:
        """Initialise the notification queue with an INotificationService adapter.

        Args:
            notifier: The concrete notification service adapter (e.g.,
                TelegramBotService). Must implement INotificationService.
        """
        self._notifier: INotificationService = notifier
        self._queue: asyncio.Queue[Promotion] = asyncio.Queue()

    async def enqueue(self, promotion: Promotion) -> None:
        """Enqueue a discovered Promotion for async delivery.

        Non-blocking — the item is placed in the queue and consumed later
        by the worker loop. The Promotion is a frozen dataclass; it is
        read-only and safe to pass by reference.

        Args:
            promotion: The newly-discovered Promotion to alert about.
        """
        await self._queue.put(promotion)

    async def worker(self) -> None:
        """Background loop that dequeues and delivers promotions indefinitely.

        Runs as an infinite `while True` loop. Blocks on queue.get() when the
        queue is empty (the orchestrator continues scanning independently).
        Each dequeued item is delivered via notifier.send_promo_alert().

        Resilience:
          - NotificationError: caught and logged at WARNING level (the adapter
            exhausted its own retries). The worker continues.
          - Exception: broad catch-all — logged at ERROR level to prevent
            any unexpected exception from crashing the worker loop.
          - self._queue.task_done() is called in a finally block to ensure
            queue accounting stays correct regardless of delivery outcome.

        Cancellation:
          - The caller (orchestrator/supervisor) should cancel the asyncio
            Task wrapping this coroutine during graceful shutdown. The
            CancelledError will propagate naturally out of the infinite loop.
        """
        while True:
            promotion = await self._queue.get()
            try:
                await self._notifier.send_promo_alert(promotion)
            except NotificationError:
                logger.warning(
                    "Notification delivery failed for promotion %s "
                    "(adapter retries exhausted). Skipping.",
                    promotion.promotion_id,
                )
            except Exception:
                logger.exception(
                    "Unexpected error delivering notification for promotion %s.",
                    promotion.promotion_id,
                )
            finally:
                self._queue.task_done()