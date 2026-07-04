"""Database seeding utility — inserts default Amazon Egypt TargetEndpoints.

Usage:
    python -m scripts.seed_targets

This script is idempotent: it uses INSERT OR IGNORE, so running it multiple
times will not create duplicate entries. It ensures the monitor has at least
the default endpoints to scan on first launch.

Default targets:
  1. Amazon Egypt Deals Page (HTML DOM) — the main deals/gold-box hub
  2. Amazon Egypt Today's Deals AJAX (JSON endpoint) — async deal widget API
"""

from __future__ import annotations

import asyncio
import logging
import time

import aiosqlite

from src.adapters.storage.migrations import run_migrations
from src.config.settings import settings

logger = logging.getLogger(__name__)

# ── Default Seed Targets ──────────────────────────────────────────────

SEED_TARGETS: list[dict] = [
    {
        "endpoint_id": "amz-eg-deals-page",
        "url": "https://www.amazon.eg/-/en/Deals/b/?ie=UTF8&node=27335274031",
        "parser_type": "html_dom",
        "poll_interval_seconds": 300,
        "active_hours_start": 6,  # UTC 06:00 = 08:00 Cairo
        "active_hours_end": 0,    # UTC 00:00 = 02:00 Cairo
        "impersonate_profile": "chrome124",
        "priority": 1,
        "enabled": 1,
    },
    {
        "endpoint_id": "amz-eg-today-deals-ajax",
        "url": "https://www.amazon.eg/-/en/async/deals/v2/getDeals",
        "parser_type": "json_endpoint",
        "poll_interval_seconds": 300,
        "active_hours_start": 6,
        "active_hours_end": 0,
        "impersonate_profile": "chrome124",
        "priority": 1,
        "enabled": 1,
    },
]

INSERT_SQL = """
    INSERT OR IGNORE INTO target_endpoints
        (endpoint_id, url, parser_type, poll_interval_seconds,
         active_hours_start, active_hours_end, impersonate_profile,
         priority, enabled, last_polled_utc, consecutive_failures,
         circuit_breaker_until_utc)
    VALUES
        (:endpoint_id, :url, :parser_type, :poll_interval_seconds,
         :active_hours_start, :active_hours_end, :impersonate_profile,
         :priority, :enabled, 0.0, 0, 0.0)
"""

COUNT_SQL = "SELECT COUNT(*) as cnt FROM target_endpoints WHERE enabled = 1"


async def seed(display: bool = True) -> dict[str, int]:
    """Run the seeding process against the configured database.

    Opens a connection, runs migrations (ensuring target_endpoints table
    exists), then inserts default targets using INSERT OR IGNORE for
    idempotency.

    Args:
        display: If True, print a human-readable summary to stdout.
            Set to False for programmatic/testing use.

    Returns:
        A dict with keys: {"inserted": int, "existing": int, "total_active": int}
    """
    inserted = 0
    existing = 0

    db = await aiosqlite.connect(settings.DB_PATH)
    try:
        # Ensure schema exists (idempotent migrations)
        await run_migrations(db)

        # Count existing enabled targets before seeding
        cursor = await db.execute(COUNT_SQL)
        row = await cursor.fetchone()
        before_count = row[0] if row else 0

        # Insert seed targets (INSERT OR IGNORE — safe to re-run)
        for target in SEED_TARGETS:
            cursor = await db.execute(INSERT_SQL, target)
            if cursor.rowcount == 1:
                inserted += 1
            else:
                existing += 1

        await db.commit()

        # Count total enabled targets after seeding
        cursor = await db.execute(COUNT_SQL)
        row = await cursor.fetchone()
        after_count = row[0] if row else 0

    finally:
        await db.close()

    if display:
        _print_summary(inserted, existing, after_count)

    return {
        "inserted": inserted,
        "existing": existing,
        "total_active": after_count,
    }


def _print_summary(inserted: int, existing: int, total_active: int) -> None:
    """Print a human-readable seeding summary to stdout."""
    print()
    print("=" * 60)
    print("  Amz-Hunt Target Endpoint Seeding Complete")
    print("=" * 60)
    print(f"  • Newly inserted:   {inserted}")
    print(f"  • Already existed:  {existing}")
    print(f"  • Total active now: {total_active}")
    print("=" * 60)
    if total_active == 0:
        print()
        print("  WARNING: No active targets in database.")
        print("  The monitor will have nothing to scan.")
    print()


async def main() -> None:
    """Entry point for seeding script."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    await seed(display=True)


if __name__ == "__main__":
    asyncio.run(main())