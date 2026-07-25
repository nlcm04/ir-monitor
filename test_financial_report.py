"""
test_financial_report.py — Live end-to-end test of the financial-report feature.

Scrapes a real financial-statement site, picks its latest filing, generates
the year-over-year income-statement DOCX (via Tesseract OCR), and sends both
the normal alert message and the DOCX to Telegram for real — ignores the DB
so you always get a message. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
in .env, and Tesseract (+ Vietnamese language data) installed locally.

Usage:
    python test_financial_report.py                # tries each financial-report site until one works
    python test_financial_report.py dhc_fin         # a specific site key only
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import financial_report
from config import SITES
from notifier import Notifier
from scrapers.base import PlaywrightScraper

# Sites whose scraped items are known to be direct PDF links tagged "Financials"
_FINANCIAL_REPORT_SITE_KEYS = ["dhc_fin", "vietjet_qfin", "tasecoairs", "ptb_fin"]


async def main() -> None:
    requested = sys.argv[1:]
    keys = requested or _FINANCIAL_REPORT_SITE_KEYS
    sites = [s for s in SITES if s["key"] in keys]
    if not sites:
        print(f"No matching site keys among: {', '.join(keys)}")
        sys.exit(1)

    notifier = Notifier()  # raises early if Telegram credentials are missing

    async with PlaywrightScraper() as scraper:
        for site in sites:
            print(f"\n=== {site['company']} ({site['key']}) ===")
            try:
                items = await scraper.scrape(site)
            except Exception as e:
                print(f"  scrape failed: {type(e).__name__}: {e}")
                continue

            fin_items = [it for it in items if financial_report.is_financial_statement(it)]
            if not fin_items:
                print("  no financial-statement PDF items found on this page")
                continue

            item = fin_items[0]
            item["site_key"] = site["key"]
            item["company"] = site["company"]
            print(f"  target: {item['title'][:70]}")
            print(f"  url:    {item['url']}")

            ok = await notifier.send_article(item)
            print(f"  alert sent: {ok}")

            print("  generating income-statement report (downloads the PDF + runs Tesseract OCR)...")
            path = await financial_report.maybe_generate_report(item)
            if path is None:
                print("  no report generated (Tesseract not installed, extraction found nothing, or download failed — see WARNING/INFO logs above for the actual cause)")
                continue  # try the next candidate site instead of giving up entirely
            print(f"  report built: {path}")

            sent = await notifier.send_document(path, caption=item["title"][:1024])
            print(f"  document sent: {sent}")
            return

    print("\nNo site yielded a financial-statement item to test with.")


asyncio.run(main())
