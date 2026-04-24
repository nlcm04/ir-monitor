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

from config import FIREFOX_HEADERS, USER_AGENTS
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

        # extra_http_headers applies to EVERY request in the context, including
        # AJAX/XHR calls made by page scripts.  Navigation-specific headers
        # (Sec-Fetch-Mode: navigate, Sec-Fetch-Site: none, Sec-Fetch-User: ?1,
        # Upgrade-Insecure-Requests) are WRONG for XHR and will cause CORS/fetch-
        # metadata checks on APIs to reject the request silently.  Only include
        # headers that are valid for both navigation and XHR.
        _CONTEXT_SAFE_HEADERS = {
            k: v for k, v in FIREFOX_HEADERS.items()
            if k not in {
                "Sec-Fetch-Dest",
                "Sec-Fetch-Mode",
                "Sec-Fetch-Site",
                "Sec-Fetch-User",
                "Upgrade-Insecure-Requests",
                "Cache-Control",  # navigation-only semantics
            }
        }

        ctx = await self._browser.new_context(
            user_agent=ua,
            locale="vi-VN",
            viewport={"width": 1366, "height": 900},
            extra_http_headers=_CONTEXT_SAFE_HEADERS,
        )
        # Strip the webdriver flag that some anti-bot checks look for.
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return ctx

    async def scrape(self, site: dict) -> list[dict]:
        """Scrape one site with automatic retries on timeout."""
        max_retries = int(os.getenv("SCRAPER_RETRIES", "2"))
        last_exc: Exception = RuntimeError("no attempts made")

        for attempt in range(1, max_retries + 1):
            try:
                if site.get("intercept_url_contains"):
                    return await self._scrape_api_intercept(site)
                if site.get("mode") == "requests":
                    return await self._scrape_requests(site)
                return await self._scrape_html(site)
            except (ScraperError, Exception) as e:
                last_exc = e
                is_timeout = "timeout" in str(e).lower() or "TimeoutError" in type(e).__name__
                is_scraper_err = isinstance(e, ScraperError)

                if attempt < max_retries and (is_timeout or is_scraper_err):
                    wait = 5 * attempt
                    log.warning(
                        "[%s] attempt %d/%d failed (%s) — retrying in %ds",
                        site["key"], attempt, max_retries, type(e).__name__, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

        raise last_exc  # should never reach here

    async def _scrape_requests(self, site: dict) -> list[dict]:
        """Lightweight HTTP-only scrape for server-side-rendered pages.

        Bypasses Playwright entirely — no browser automation fingerprint, no
        waiting for third-party CDN/analytics scripts that hang on cloud IPs.
        Uses aiohttp with full Firefox headers so the server sees a real browser.
        """
        import aiohttp

        ua = random.choice(USER_AGENTS)
        headers = {**FIREFOX_HEADERS, "User-Agent": ua}
        # Merge any site-level extra headers (e.g. Referer)
        headers.update(site.get("extra_headers", {}))

        timeout = aiohttp.ClientTimeout(total=60)
        connector = aiohttp.TCPConnector(ssl=False)  # skip cert issues on VN hosting

        log.info("[%s] requests-mode GET %s", site["key"], site["url"])
        async with aiohttp.ClientSession(
            headers=headers,
            connector=connector,
            timeout=timeout,
        ) as session:
            async with session.get(site["url"]) as resp:
                resp.raise_for_status()
                html = await resp.text(errors="replace")

        items = self._parse(html, site)
        if not items:
            raise ScraperError(
                f"No items parsed for {site['key']} (requests mode) — selectors may be stale"
            )
        return items

    async def _scrape_html(self, site: dict) -> list[dict]:
        """Standard HTML scrape via CSS selectors."""
        ctx = await self._new_context()
        page: Page = await ctx.new_page()
        timeout = int(os.getenv("NAV_TIMEOUT_MS", "90000"))

        # Sites that need full JS execution use networkidle; others use faster domcontentloaded
        load_strategy = site.get("wait_until", "domcontentloaded")

        try:
            log.info("[%s] GET %s (strategy=%s)", site["key"], site["url"], load_strategy)
            await page.goto(site["url"], wait_until=load_strategy, timeout=timeout)

            if site.get("wait_for"):
                try:
                    await page.wait_for_selector(site["wait_for"], timeout=timeout)
                except PwTimeout:
                    log.warning("[%s] wait_for selector timed out; parsing anyway", site["key"])

            if site.get("scroll"):
                await self._auto_scroll(page)

            await asyncio.sleep(random.uniform(1.5, 3.0))
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

    async def _scrape_api_intercept(self, site: dict) -> list[dict]:
        """Load the page, intercept JSON API responses, and parse them directly.

        Useful for sites that render news via JavaScript/AJAX (Dohaco FPTS widget,
        Vietnam Airlines AEM) where CSS selectors can't reach the content.
        """
        import json as _json

        pattern = site["intercept_url_contains"]
        captured: list[dict] = []

        ctx = await self._new_context()
        page: Page = await ctx.new_page()
        timeout = int(os.getenv("NAV_TIMEOUT_MS", "90000"))

        async def on_response(response):
            if pattern in response.url:
                log.info("[%s] intercepted API: %s (HTTP %s)", site["key"], response.url[:120], response.status)
                try:
                    data = await response.json()
                    captured.append(data)
                    log.info("[%s] captured response (%d bytes)", site["key"], len(str(data)))
                except Exception as exc:
                    log.warning("[%s] could not parse intercepted response: %s", site["key"], exc)

        page.on("response", on_response)
        # Default to networkidle for full-JS sites; domcontentloaded is faster for
        # sites whose AJAX widgets fire quickly (e.g. Dohaco FPTS widget) and where
        # networkidle would block on unrelated third-party CDN scripts.
        intercept_wait = site.get("intercept_wait_until", "networkidle")
        intercept_sleep = int(site.get("intercept_sleep", 5))
        try:
            log.info("[%s] API-intercept GET %s (wait=%s)", site["key"], site["url"], intercept_wait)
            await page.goto(site["url"], wait_until=intercept_wait, timeout=timeout)
            await asyncio.sleep(intercept_sleep)  # allow lazy API calls to fire
        finally:
            await page.close()
            await ctx.close()

        if not captured:
            raise ScraperError(
                f"No API responses intercepted for {site['key']} — "
                f"pattern '{pattern}' not matched"
            )

        parser = site.get("intercept_parser", "generic")
        items: list[dict] = []

        if parser == "fpts":
            # FPTS API: multiple requests (cbtt=0 and cbtt=1). Each response is
            # {"Data": {"Table1": [{"Title":..., "DatePub":..., "URL":...}]}}
            seen_ids: set = set()
            for resp in captured:
                for row in resp.get("Data", {}).get("Table1", []):
                    sid = row.get("SID")
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    title = (row.get("Title") or "").strip()
                    url = (row.get("URL") or "").replace("\\", "/")
                    if not url.startswith("http"):
                        url = "https://file.fpts.com.vn" + url
                    pub = _parse_date(row.get("DatePub", ""), ["%d/%m/%Y %H:%M"])
                    if title and url:
                        items.append({"title": title, "url": url, "published": pub})

        elif parser == "vna_jcr":
            # VNA AEM API: {"YYYY": {"items": [{"path":..., "title":...}]}}
            # Multiple responses (one per year). Merge all items.
            seen_paths: set = set()
            base_article_url = site.get("article_base_url", "")
            for resp in captured:
                for year_data in resp.values():
                    if not isinstance(year_data, dict):
                        continue
                    for item in year_data.get("items", []):
                        path = item.get("path", "")
                        if path in seen_paths:
                            continue
                        seen_paths.add(path)
                        title = (item.get("title") or "").strip()
                        # Derive public URL from the last path segment
                        slug = path.rstrip("/").split("/")[-1]
                        url = f"{base_article_url}/{slug}" if base_article_url else path
                        pub = _parse_date(item.get("publishedDate", ""), ["%Y-%m-%dT%H:%M:%S"])
                        if title and url:
                            items.append({"title": title, "url": url, "published": pub})

        if not items:
            raise ScraperError(
                f"API responses captured but no items parsed for {site['key']}"
            )
        return items[:40]

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
            # When the item node itself is the <a> tag (self_is_link sites)
            if site.get("self_is_link") and node.name == "a":
                title = node.get_text(" ", strip=True).strip()
                href = (node.get("href") or "").strip()
                pub = None
            else:
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

            # Date (skip for self_is_link sites — pub already set to None above)
            if not site.get("self_is_link"):
                pub = None
                if site.get("date"):
                    date_el = node.select_one(site["date"])
                    if date_el:
                        pub = _parse_date(date_el.get_text(" ", strip=True), site.get("date_formats", []))

            # Vietjet: date prefix "17/04/2026: headline" → strip to get clean title
            if site.get("strip_date_prefix"):
                title = re.sub(r"^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\s*:\s*", "", title).strip()

            # ACV: date suffix "headline (123) 08:34 | 16/04/2026" → extract date, clean title
            if site.get("strip_date_suffix"):
                m = re.search(r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*$", title)
                if m:
                    pub = _parse_date(m.group(1), site.get("date_formats", []))
                    title = title[:m.start()].rstrip("| :0123456789").strip()

            # SASCO: second link for each article has the full URL as its text — skip it
            if site.get("filter_url_text_links") and title.startswith("http"):
                continue

            if not title or len(title) < 5:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            out.append({"title": title, "url": url, "published": pub})

        # Many layouts include 20-50+ items; cap to avoid giant first-run floods.
        return out[:40]
