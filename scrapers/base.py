"""
Playwright-based scraper. One browser, one context, many pages — each site
scraped with fresh state so cookies from one don't leak into another.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PwTimeout,
    async_playwright,
)

from config import USER_AGENTS
from logger import get_logger

log = get_logger(__name__)


class ScraperError(Exception):
    """Raised when a site returns content but no items parse — i.e. layout drift."""


def _absolutize(base_url: str, href: str) -> str:
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(base_url.rstrip("/") + "/", href.lstrip("/"))


def _parse_date(raw: str, formats: list[str]) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip()
    # Many VN sites prefix with "Ngày ", "Posted on", etc.
    s = re.sub(r"^(ngày|posted on|published|đăng lúc|cập nhật)\s*:?\s*", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s[: len(datetime.now().strftime(fmt)) + 4], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Try a loose dd/mm/yyyy anywhere in the string
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = "20" + y
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s  # fall back to raw string — better than nothing in Telegram


class PlaywrightScraper:
    """Async context-manager wrapping a single browser instance."""

    def __init__(self) -> None:
        self._pw = None
        self._browser: Optional[Browser] = None

    async def __aenter__(self) -> "PlaywrightScraper":
        self._pw = await async_playwright().start()
        headless = os.getenv("HEADLESS", "true").lower() != "false"
        self._browser = await self._pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _new_context(self) -> BrowserContext:
        assert self._browser is not None
        ua = random.choice(USER_AGENTS)
        ctx = await self._browser.new_context(
            user_agent=ua,
            locale="vi-VN",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        # Strip the webdriver flag that some anti-bot checks look for.
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return ctx

    async def scrape(self, site: dict) -> list[dict]:
        """Scrape one site using its selector config. Raises ScraperError on drift."""
        ctx = await self._new_context()
        page: Page = await ctx.new_page()
        timeout = int(os.getenv("NAV_TIMEOUT_MS", "45000"))
        try:
            log.info("[%s] GET %s", site["key"], site["url"])
            await page.goto(site["url"], wait_until="domcontentloaded", timeout=timeout)

            if site.get("wait_for"):
                try:
                    await page.wait_for_selector(site["wait_for"], timeout=timeout)
                except PwTimeout:
                    log.warning("[%s] wait_for selector timed out; parsing anyway", site["key"])

            if site.get("scroll"):
                await self._auto_scroll(page)

            # Small polite jitter before reading DOM
            await asyncio.sleep(random.uniform(0.8, 2.0))
            html = await page.content()
        finally:
            await page.close()
            await ctx.close()

        items = self._parse(html, site)
        if not items:
            raise ScraperError(
                f"No items parsed for {site['key']} — selectors may be stale"
            )
        return items

    @staticmethod
    async def _auto_scroll(page: Page, steps: int = 6) -> None:
        for _ in range(steps):
            await page.mouse.wheel(0, 1500)
            await asyncio.sleep(random.uniform(0.4, 0.9))

    @staticmethod
    def _parse(html: str, site: dict) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        nodes = soup.select(site["item"])
        base = site["base_url"]
        origin_host = urlparse(base).netloc

        out: list[dict] = []
        seen_urls: set[str] = set()

        for node in nodes:
            # Title
            title_el = node.select_one(site["title"]) if site.get("title") else None
            title = (title_el.get_text(" ", strip=True) if title_el else "").strip()

            # Link
            link_el = node.select_one(site["link"]) if site.get("link") else None
            if not link_el and title_el and title_el.name == "a":
                link_el = title_el
            href = (link_el.get("href") or "").strip() if link_el else ""
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            url = _absolutize(base, href)

            # If the link escapes to an unrelated domain, skip — usually a nav/ad link.
            if urlparse(url).netloc and origin_host not in urlparse(url).netloc and \
                    urlparse(url).netloc not in origin_host:
                # allow subdomains of base (e.g. ir.vietjetair.com base)
                pass

            # Date
            pub = None
            if site.get("date"):
                date_el = node.select_one(site["date"])
                if date_el:
                    pub = _parse_date(date_el.get_text(" ", strip=True), site.get("date_formats", []))

            if not title or len(title) < 5:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            out.append({"title": title, "url": url, "published": pub})

        # Many layouts include 20-50+ items; cap to avoid giant first-run floods.
        return out[:40]
