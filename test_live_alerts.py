"""
Scrapes every site, takes the latest article from each,
and sends it to Telegram — ignores the DB so you always get a message.

Usage:
    python test_live_alerts.py
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import SITES
from notifier import Notifier
from scrapers.base import PlaywrightScraper, ScraperError


async def main() -> None:
    notifier = Notifier()
    results: list[tuple[str, str, str]] = []  # (company, status, detail)

    print(f"\nScraping {len(SITES)} sites and sending latest article from each...\n")

    async with PlaywrightScraper() as scraper:
        for site in SITES:
            print(f"  → {site['company']} ...", end=" ", flush=True)
            try:
                items = await scraper.scrape(site)
                latest = items[0]  # most recent article
                latest["site_key"] = site["key"]
                latest["company"] = site["company"]

                ok = await notifier.send_article(latest)
                if ok:
                    print(f"✅ sent: {latest['title'][:60]}")
                    results.append((site["company"], "✅ sent", latest["title"][:60]))
                else:
                    print("❌ Telegram send failed")
                    results.append((site["company"], "❌ send failed", ""))

            except ScraperError as e:
                print(f"❌ scrape error: {e}")
                results.append((site["company"], "❌ scrape failed", str(e)))
            except Exception as e:
                print(f"❌ unexpected: {e}")
                results.append((site["company"], "❌ error", str(e)))

            await asyncio.sleep(2)  # polite gap between sites + Telegram rate limit

    print("\n" + "─" * 60)
    print("SUMMARY")
    print("─" * 60)
    for company, status, detail in results:
        print(f"  {status}  {company}")
        if detail and "failed" in status or "error" in status:
            print(f"         {detail}")

    passed = sum(1 for _, s, _ in results if "✅" in s)
    print(f"\n  {passed}/{len(results)} sites sent successfully to Telegram\n")


asyncio.run(main())
