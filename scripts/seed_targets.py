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
# NOTE: Amazon Egypt rotates category-specific deal URLs frequently.
#       The canonical deals homepage (below) is the most reliable live entry point.

SEED_TARGETS: list[dict] = [
    {
        "endpoint_id": "amz-eg-deals-page",
        "url": "https://www.amazon.eg/-/en/deals",
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
        # TEMPORARILY DEACTIVATED (enabled=0): Amazon Egypt changed internal
        # AJAX routing for /async/deals/ — this endpoint currently returns
        # 404/no content. When a new working AJAX URL is discovered, update
        # the url field and re-enable by setting enabled=1.
        "url": "https://www.amazon.eg/-/en/async/deals/v2/getDeals",
        "parser_type": "json_endpoint",
        "poll_interval_seconds": 300,
        "active_hours_start": 6,
        "active_hours_end": 0,
        "impersonate_profile": "chrome124",
        "priority": 1,
        "enabled": 0,
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

UPDATE_SQL = """
    UPDATE target_endpoints
    SET url = :url,
        parser_type = :parser_type,
        poll_interval_seconds = :poll_interval_seconds,
        active_hours_start = :active_hours_start,
        active_hours_end = :active_hours_end,
        impersonate_profile = :impersonate_profile,
        priority = :priority,
        enabled = :enabled
    WHERE endpoint_id = :endpoint_id
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

        # ── Upsert seed targets ───────────────────────────────────────
        # Strategy:
        #   1. UPDATE existing rows so URLs/enabled flags are refreshed.
        #   2. INSERT OR IGNORE for rows that don't yet exist.
        # This ensures running the seeding script corrects stale data even
        # when target rows are already present in the database.
        for target in SEED_TARGETS:
            # Attempt UPDATE first — if the endpoint_id exists, refresh all
            # config fields (url, enabled, parser_type, intervals, etc.)
            # but preserve runtime state (last_polled_utc, failures, cooldown).
            update_cursor = await db.execute(UPDATE_SQL, target)
            updated = update_cursor.rowcount  # -1 on SQLite, but we check below

            # Now INSERT OR IGNORE for the case where the row didn't exist.
            insert_cursor = await db.execute(INSERT_SQL, target)
            if insert_cursor.rowcount == 1:
                inserted += 1
            else:
                # INSERT did nothing — row already existed (now updated above).
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