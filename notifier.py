"""Telegram notifier — formats analyst-focused alerts + admin error pings."""

from __future__ import annotations

import asyncio
import html
import os
from pathlib import Path
from typing import Iterable

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from unidecode import unidecode

from config import FLAG_KEYWORDS
from logger import get_logger

log = get_logger(__name__)


def _flags_for(title: str) -> list[str]:
    """Accent- and case-insensitive keyword match. Returns list of tag labels."""
    hay = unidecode(title).lower()
    flags: list[str] = []
    for kw, label in FLAG_KEYWORDS:
        if unidecode(kw).lower() in hay and label not in flags:
            flags.append(label)
    return flags


def _format_message(item: dict) -> str:
    company = html.escape(item["company"])
    title = html.escape(item["title"])
    date = html.escape(item.get("published") or "—")
    url = item["url"]  # href attribute, not escaped

    flags = _flags_for(item["title"])
    meta = [company]
    if flags:
        meta.append(" / ".join(flags))
    meta.append(date)

    return (
        f"<i>{' · '.join(meta)}</i>\n"
        f'<a href="{html.escape(url, quote=True)}"><b>{title}</b></a>'
    )


class Notifier:
    def __init__(self) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env"
            )
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID") or chat_id

    async def send_article(self, item: dict, retries: int = 3) -> bool:
        msg = _format_message(item)
        for attempt in range(1, retries + 1):
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=msg,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=15,
                )
                return True
            except TelegramError as e:
                if attempt < retries:
                    wait = 2 ** attempt  # 2s, 4s
                    log.warning(
                        "Telegram send attempt %d/%d failed (%s) — retrying in %ds",
                        attempt, retries, e, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    log.error("Telegram send failed for %s: %s", item.get("url"), e)
        return False

    async def send_many(self, items: Iterable[dict]) -> list[dict]:
        """Send alerts sequentially with small spacing to respect rate limits.

        Returns the subset of `items` that failed to send (after their own
        internal retries), so the caller can tell delivered items apart from
        ones that never went out and must not be marked as processed."""
        failed: list[dict] = []
        for it in items:
            ok = await self.send_article(it)
            if not ok:
                failed.append(it)
            await asyncio.sleep(1.2)  # ~30 msgs/min, well under Telegram cap
        return failed

    async def send_document(self, path: Path, caption: str = "") -> bool:
        try:
            with open(path, "rb") as f:
                await self.bot.send_document(
                    chat_id=self.chat_id,
                    document=f,
                    filename=path.name,
                    caption=caption[:1024] if caption else None,
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=15,
                )
            return True
        except TelegramError as e:
            log.error("Telegram document send failed for %s: %s", path.name, e)
            return False

    async def send_admin(self, text: str) -> None:
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_notification=True,  # silent admin ping
            )
        except TelegramError as e:
            log.error("Admin Telegram send failed: %s", e)
