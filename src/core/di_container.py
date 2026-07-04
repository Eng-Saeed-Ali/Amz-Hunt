"""DIContainer — Composition Root that assembles adapters and wires the Orchestrator.

This is the ONLY file in src/core/ permitted to import from src.adapters.*.
It follows the Dependency Inversion Principle: high-level core logic depends on
Protocols; this container is the single point where concrete adapter choices are
made and everything is wired together.
"""

from __future__ import annotations

from src.adapters.http.curl_cffi_client import CurlCffiClient
from src.adapters.notification.telegram_bot import TelegramBotNotifier
from src.adapters.parsers.html_dom_parser import HTMLDOMParser
from src.adapters.parsers.json_endpoint_parser import JSONEndpointParser
from src.adapters.storage.sqlite_backend import SQLiteBackend
from src.config.settings import settings
from src.core.dedup_engine import DedupEngine
from src.core.notification_queue import NotificationQueue
from src.core.orchestrator import ScanOrchestrator
from src.core.parser_router import ParserRouter
from src.core.scheduler import ActiveHoursScheduler
from src.core.validator import KeywordValidator


class DIContainer:
    """Composition Root — builds the full object graph and returns the wired Orchestrator.

    This class owns the lifecycle of all adapter instances (storage, HTTP client,
    notification service) and core domain services. After build() completes, the
    returned ScanOrchestrator has every dependency injected and is ready to run.

    The entry point (scripts/run_monitor.py) must also access:
      - container.storage: to fetch TargetEndpoints before starting the loop
      - container.queue: to start the NotificationQueue.worker() background task

    Lifecycle:
        1. container = DIContainer()
        2. orchestrator = await container.build()
        3. endpoints = await container.storage.get_active_targets()
        4. worker_task = asyncio.create_task(container.queue.worker())
        5. await orchestrator.run_forever(endpoints)
        6. On shutdown: cancel tasks, await container.storage.close()
    """

    def __init__(self) -> None:
        """Initialise an empty container. Call build() to wire everything."""
        self._storage: SQLiteBackend | None = None
        self._http_client: CurlCffiClient | None = None
        self._telegram: TelegramBotNotifier | None = None
        self._html_parser: HTMLDOMParser | None = None
        self._json_parser: JSONEndpointParser | None = None
        self._router: ParserRouter | None = None
        self._dedup: DedupEngine | None = None
        self._scheduler: ActiveHoursScheduler | None = None
        self._validator: KeywordValidator | None = None
        self._queue: NotificationQueue | None = None
        self._orchestrator: ScanOrchestrator | None = None

    @property
    def storage(self) -> SQLiteBackend:
        """Expose the storage backend for the entry point (get_active_targets)."""
        if self._storage is None:
            raise RuntimeError("DIContainer.build() must be called before accessing storage")
        return self._storage

    @property
    def queue(self) -> NotificationQueue:
        """Expose the notification queue for the entry point (worker task)."""
        if self._queue is None:
            raise RuntimeError("DIContainer.build() must be called before accessing queue")
        return self._queue

    async def build(self) -> ScanOrchestrator:
        """Assemble all adapters, core services, and return the wired Orchestrator.

        Steps:
          1. Instantiate all concrete adapters (storage, HTTP, parsers, Telegram)
          2. Open the SQLite connection and run migrations
          3. Build core domain services (router, dedup, scheduler, validator, queue)
          4. Wire the ScanOrchestrator with all 7 dependencies
          5. Return the ready-to-run orchestrator

        Returns:
            A fully-injected ScanOrchestrator ready for run_forever().

        Raises:
            RuntimeError: If any adapter fails to initialise (missing .env, etc.).
        """
        # ── 1. Instantiate Adapters ───────────────────────────────────
        self._storage = SQLiteBackend(db_path=settings.DB_PATH)
        await self._storage.connect()  # Opens DB, runs migrations, enables WAL

        self._http_client = CurlCffiClient(
            default_impersonate=settings.DEFAULT_IMPERSONATE_PROFILE,
        )
        self._telegram = TelegramBotNotifier(
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            chat_id=settings.TELEGRAM_CHAT_ID,
        )
        self._html_parser = HTMLDOMParser()
        self._json_parser = JSONEndpointParser()

        # ── 2. Assemble Core Domain Services ──────────────────────────
        self._router = ParserRouter(
            parsers={
                "html_dom": self._html_parser,
                "json_endpoint": self._json_parser,
            }
        )
        self._dedup = DedupEngine(storage=self._storage)
        self._scheduler = ActiveHoursScheduler()
        self._validator = KeywordValidator()
        self._queue = NotificationQueue(notifier=self._telegram)

        # ── 3. Wire the Orchestrator ──────────────────────────────────
        self._orchestrator = ScanOrchestrator(
            storage=self._storage,
            http_client=self._http_client,
            router=self._router,
            dedup=self._dedup,
            scheduler=self._scheduler,
            validator=self._validator,
            queue=self._queue,
        )

        return self._orchestrator