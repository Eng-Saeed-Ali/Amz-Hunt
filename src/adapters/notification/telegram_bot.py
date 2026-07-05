"""Telegram Bot API adapter — implements INotificationService using aiohttp."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import time
from typing import TYPE_CHECKING

import aiohttp

from src.core.models.exceptions import NotificationError
from src.core.models.notification import NotificationResult
from src.core.models.promotion import Promotion
from src.core.ports.notification import INotificationService

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class TelegramBotNotifier:
    """Telegram Bot API notification service using raw aiohttp.

    Implements INotificationService with:
    - Exponential backoff retries (250ms → 500ms → 1s → 2s → 4s)
    - HTML parse mode with proper escaping
    - Web page preview disabled for promo alerts
    - All network/API errors wrapped in NotificationError
    - Returns NotificationResult for every attempt

    Args:
        bot_token: Telegram Bot API token from @BotFather.
        chat_id: Target chat ID (can be int or str like "@channelusername").
        base_url: Telegram API base URL (default: https://api.telegram.org).
    """

    # Retry delays in seconds (exponential backoff)
    RETRY_DELAYS: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0)

    # Severity emoji mapping
    SEVERITY_EMOJI: dict[str, str] = {
        "info": "\u2139\ufe0f",
        "warning": "\u26a0\ufe0f",
        "critical": "\U0001f6a8",
    }

    def __init__(
        self,
        bot_token: str,
        chat_id: str | int,
        base_url: str = "https://api.telegram.org",
    ) -> None:
        if not bot_token:
            raise ValueError("bot_token must not be empty")
        if not chat_id:
            raise ValueError("chat_id must not be empty")

        self._bot_token = bot_token
        self._chat_id = str(chat_id)
        self._base_url = base_url.rstrip("/")
        self._api_url = f"{self._base_url}/bot{self._bot_token}"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30.0)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> TelegramBotNotifier:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # ── INotificationService Protocol Implementation ──────────────────

    async def send_promo_alert(self, promotion: Promotion) -> NotificationResult:
        """Send a promotion alert to Telegram with a beautified Arabic HTML template.

        Format (HTML):
        🔥 <b>صيد جديد من عروض أمازون مصر!</b>
        ━━━━━━━━━━━━━━━━━━
        📦 <b>المنتج:</b>
        <i>{title}</i>

        💰 <b>السعر في العرض:</b> <code>{deal_price}</code>
        <s>❌ <b>السعر الأصلي:</b> {list_price}</s>  ← only if list_price exists
        ━━━━━━━━━━━━━━━━━━
        🔗 <b>رابط القنص المباشر:</b>
        👉 <a href="{url}">اضغط هنا للانتقال إلى العرض</a>

        🕒 <code>{timestamp}</code> | 🛰️ <code>{source}</code>

        Prices are extracted from promotion.content_snippet (JSON from
        the embedded productSearchResponse payload).  If JSON parsing
        fails, falls back to a simplified template using promotion.title
        which may contain the old enriched format.

        Args:
            promotion: The Promotion to alert about.

        Returns:
            NotificationResult with success flag, message_id, or error.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(promotion.first_seen_utc))

        # Source endpoint hint (truncated for display)
        source_hint = promotion.source_endpoint_id
        if len(source_hint) > 80:
            source_hint = source_hint[:77] + "..."

        # ── Prices from Promotion model ─────────────────────────────
        deal_price_str: str | None = promotion.deal_price
        list_price_str: str | None = promotion.list_price

        # ── Escape user-provided content for HTML ────────────────────
        safe_title = html.escape(promotion.title)
        safe_url = html.escape(promotion.url)
        safe_source = html.escape(source_hint)

        # ── Build the beautified Arabic template ─────────────────────
        if deal_price_str:
            # Full template with prices extracted from JSON
            lines: list[str] = [
                "🔥 <b>صيد جديد من عروض أمازون مصر!</b>",
                "━━━━━━━━━━━━━━━━━━",
                "📦 <b>المنتج:</b>",
                f"<i>{safe_title}</i>",
                "",
                f"💰 <b>السعر في العرض:</b> <code>{deal_price_str}</code>",
            ]
            # List price with strikethrough (only if available)
            if list_price_str:
                safe_list = html.escape(list_price_str)
                lines.append(
                    f"<s>❌ <b>السعر الأصلي:</b> {safe_list}</s>"
                )
            lines.extend([
                "━━━━━━━━━━━━━━━━━━",
                "🔗 <b>رابط العرض المباشر:</b>",
                f'👉 <a href="{safe_url}">اضغط هنا للانتقال إلى العرض</a>',
                "",
                f"🕒 <code>{timestamp}</code> | 🛰️ <code>{safe_source}</code>",
            ])
            message = "\n".join(lines)
        else:
            # Fallback: simple template when prices not extractable
            message = (
                "🔥 <b>صيد جديد من عروض أمازون مصر!</b>\n\n"
                f"<b>{safe_title}</b>\n"
                f'<a href="{safe_url}">اضغط هنا للانتقال إلى العرض</a>\n\n'
                f"🕒 <code>{timestamp}</code> | 🛰️ <code>{safe_source}</code>"
            )

        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": False,
        }

        return await self._send_with_retry("sendMessage", payload)

    async def send_health_check(self, status: dict[str, int]) -> NotificationResult:
        """Send a system health check to Telegram.

        Format (HTML):
        ℹ️ <b>Health Check</b>

        📊 Total Scans: {total}
        ✅ New Promos: {success_new}
        📄 No Change: {success_no_change}
        🚫 Blocked: {blocked}
        ⚠️ Errors: {errors}
        ⏭️ Skipped: {skipped}

        Args:
            status: Dict with scan statistics.

        Returns:
            NotificationResult with success flag, message_id, or error.
        """
        lines = [
            "ℹ️ <b>Health Check</b>",
            "",
            f"📊 Total Scans: {status.get('total_scans', 0)}",
            f"✅ New Promos: {status.get('success_new', 0)}",
            f"📄 No Change: {status.get('success_no_change', 0)}",
            f"🚫 Blocked: {status.get('blocked', 0)}",
            f"⚠️ Errors: {status.get('errors', 0)}",
            f"⏭️ Skipped: {status.get('skipped_cooldown', 0)}",
        ]

        message = "\n".join(lines)

        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": True,  # Silent for health checks
        }

        return await self._send_with_retry("sendMessage", payload)

    async def send_error_alert(self, message: str, severity: str = "warning") -> NotificationResult:
        """Send an error/warning alert to Telegram.

        Format (HTML):
        {emoji} <b>{Severity} Alert</b>

        {message}

        Args:
            message: The alert message text.
            severity: "info", "warning", or "critical".

        Returns:
            NotificationResult with success flag, message_id, or error.
        """
        emoji = self.SEVERITY_EMOJI.get(severity.lower(), "\u26a0\ufe0f")
        severity_label = severity.capitalize()

        safe_message = html.escape(message)

        formatted = (
            f"{emoji} <b>{severity_label} Alert</b>\n\n"
            f"{safe_message}"
        )

        payload = {
            "chat_id": self._chat_id,
            "text": formatted,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": severity.lower() == "info",
        }

        return await self._send_with_retry("sendMessage", payload)

    # ── Internal Helpers ──────────────────────────────────────────────

    async def _send_with_retry(self, method: str, payload: dict) -> NotificationResult:
        """Send a Telegram API request with exponential backoff retries.

        Args:
            method: Telegram Bot API method name (e.g., "sendMessage").
            payload: Request payload dict.

        Returns:
            NotificationResult with outcome.
        """
        url = f"{self._api_url}/{method}"
        session = await self._get_session()

        last_error: Exception | None = None

        for attempt, delay in enumerate(self.RETRY_DELAYS):
            try:
                async with session.post(url, json=payload) as response:
                    response_text = await response.text()

                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        raise NotificationError(f"Invalid JSON response from Telegram: {e}") from e

                    if response.status == 200 and data.get("ok"):
                        message_id = str(data.get("result", {}).get("message_id", ""))
                        return NotificationResult(
                            success=True,
                            channel="telegram",
                            message_id=message_id if message_id else None,
                            error=None,
                            timestamp_utc=time.time(),
                        )

                    # Telegram API error
                    error_desc = data.get("description", "Unknown Telegram API error")
                    error_code = data.get("error_code", response.status)

                    # Check if we should retry (429 Too Many Requests, 5xx)
                    if response.status == 429 or (500 <= response.status < 600):
                        # Extract retry_after from response if available
                        retry_after = data.get("parameters", {}).get("retry_after", delay)
                        if attempt < len(self.RETRY_DELAYS) - 1:
                            await asyncio.sleep(retry_after)
                            continue

                    # Non-retryable error or retries exhausted
                    return NotificationResult(
                        success=False,
                        channel="telegram",
                        message_id=None,
                        error=f"Telegram API error {error_code}: {error_desc}",
                        timestamp_utc=time.time(),
                    )

            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < len(self.RETRY_DELAYS) - 1:
                    await asyncio.sleep(delay)
                    continue
            except aiohttp.ClientError as e:
                last_error = e
                if attempt < len(self.RETRY_DELAYS) - 1:
                    await asyncio.sleep(delay)
                    continue
            except Exception as e:
                # Unexpected error — log the full traceback, then return gracefully
                logger.exception("Unexpected error in Telegram notification %s", method)
                return NotificationResult(
                    success=False,
                    channel="telegram",
                    message_id=None,
                    error=f"Unexpected error: {type(e).__name__}: {e}",
                    timestamp_utc=time.time(),
                )

        # All retries exhausted
        error_msg = f"Failed after {len(self.RETRY_DELAYS)} attempts"
        if last_error:
            error_msg += f": {type(last_error).__name__}: {last_error}"

        return NotificationResult(
            success=False,
            channel="telegram",
            message_id=None,
            error=error_msg,
            timestamp_utc=time.time(),
        )