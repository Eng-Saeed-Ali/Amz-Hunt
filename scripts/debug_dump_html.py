"""Debug script: fetch Amazon Egypt deals page and save raw HTML for CSS selector analysis.

Usage:
    python -m scripts.debug_dump_html

Output:
    debug_deals.html in the project root directory.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from src.adapters.http.curl_cffi_client import CurlCffiClient
from src.core.models.exceptions import HttpClientError

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "debug_deals.html"
DEALS_URL = "https://www.amazon.eg/-/en/deals"


async def main() -> None:
    print(f"[*] Instantiating CurlCffiClient (chrome124) ...")
    client = CurlCffiClient(default_impersonate="chrome124")

    async with client:
        print(f"[*] Fetching {DEALS_URL} ...")
        try:
            response = await client.fetch(DEALS_URL, impersonate="chrome124")
        except HttpClientError as e:
            print(f"[!] Network error: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[+] HTTP {response.status_code} — {len(response.body):,} bytes — {response.latency_ms:.0f}ms")

    OUTPUT_FILE.write_text(response.body, encoding="utf-8")
    print(f"[+] HTML written to {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size:,} bytes)")

    print("[*] Done. Open debug_deals.html and inspect for current CSS selectors.")


if __name__ == "__main__":
    asyncio.run(main())