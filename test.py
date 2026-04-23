"""
Test suite to verify the system works without waiting for real new articles.

Usage:
    python test.py                  # run all tests
    python test.py --telegram       # only test Telegram connection
    python test.py --scrape vietjet # only test scraping one site
    python test.py --force-alert    # send a fake article alert to Telegram
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()


# ─── helpers ──────────────────────────────────────────────────────────────────

def ok(msg: str) -> None:
    print(f"  ✅  {msg}")

def fail(msg: str) -> None:
    print(f"  ❌  {msg}")

def header(msg: str) -> None:
    print(f"\n{'─'*50}\n  {msg}\n{'─'*50}")


# ─── 1. Telegram ──────────────────────────────────────────────────────────────

async def test_telegram() -> bool:
    header("TEST 1 — Telegram connection")
    try:
        from notifier import Notifier
        n = Notifier()
        await n.bot.get_me()
        me = await n.bot.get_me()
        ok(f"Bot authenticated: @{me.username}")
    except Exception as e:
        fail(f"Bot auth failed: {e}")
        return False

    try:
        await n.send_admin("✅ <b>IR Monitor</b> — Telegram connection test passed.")
        ok("Test message sent to admin chat — check Telegram now")
    except Exception as e:
        fail(f"Send failed: {e}")
        return False

    return True


# ─── 2. Database ──────────────────────────────────────────────────────────────

def test_database() -> bool:
    header("TEST 2 — SQLite database")
    try:
        import database
        database.init_db()
        ok("DB initialised at data/ir_monitor.db")
    except Exception as e:
        fail(f"init_db failed: {e}")
        return False

    dummy = {
        "fingerprint": "test_fingerprint_000",
        "site_key": "test",
        "company": "Test Co",
        "title": "Test article",
        "url": "https://example.com/test",
        "published": "2026-01-01",
    }

    try:
        new = database.filter_new("test", "Test Co", [{"title": dummy["title"], "url": dummy["url"], "published": dummy["published"]}])
        ok(f"filter_new works — returned {len(new)} item(s)")
        if new:
            new[0]["fingerprint"] = dummy["fingerprint"]
            new[0]["site_key"] = dummy["site_key"]
            new[0]["company"] = dummy["company"]
            database.record(new)
            ok("record() works")
            again = database.filter_new("test", "Test Co", [{"title": dummy["title"], "url": dummy["url"], "published": dummy["published"]}])
            if len(again) == 0:
                ok("Deduplication works — same article not returned twice")
            else:
                fail("Deduplication FAILED — same article returned again")
                return False
    except Exception as e:
        fail(f"DB operations failed: {e}")
        return False

    return True


# ─── 3. Forced alert (fake article) ───────────────────────────────────────────

async def test_force_alert() -> bool:
    header("TEST 3 — Forced Telegram alert (fake article)")
    fake_items = [
        {
            "fingerprint": "fake_001",
            "site_key": "vietjet",
            "company": "Vietjet Air (VJC)",
            "title": "Thông báo chi trả cổ tức năm 2025 và họp ĐHĐCĐ thường niên [TEST]",
            "url": "https://ir.vietjetair.com/test",
            "published": "2026-04-24",
        },
        {
            "fingerprint": "fake_002",
            "site_key": "acv",
            "company": "ACV (Tổng Công ty Cảng HKVN)",
            "title": "Báo cáo tài chính quý 1/2026 [TEST]",
            "url": "https://acv.vn/test",
            "published": "2026-04-24",
        },
    ]
    try:
        from notifier import Notifier
        n = Notifier()
        sent = await n.send_many(fake_items)
        ok(f"Sent {sent}/{len(fake_items)} fake alerts — check Telegram")
    except Exception as e:
        fail(f"Force alert failed: {e}")
        return False
    return True


# ─── 4. Live scrape ───────────────────────────────────────────────────────────

async def test_scrape(site_key: str) -> bool:
    header(f"TEST 4 — Live scrape: {site_key}")
    from config import SITES
    site = next((s for s in SITES if s["key"] == site_key), None)
    if not site:
        fail(f"Unknown site key '{site_key}'. Valid keys: {[s['key'] for s in SITES]}")
        return False

    try:
        from scrapers.base import PlaywrightScraper, ScraperError
        async with PlaywrightScraper() as scraper:
            items = await scraper.scrape(site)
        ok(f"Scraped {len(items)} articles from {site['company']}")
        print()
        for i, it in enumerate(items[:5], 1):
            print(f"  {i}. [{it.get('published') or '—'}] {it['title'][:80]}")
            print(f"     {it['url']}")
        if len(items) > 5:
            print(f"  … and {len(items)-5} more")
    except Exception as e:
        fail(f"Scrape failed: {e}")
        return False
    return True


# ─── main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telegram", action="store_true", help="Test Telegram only")
    parser.add_argument("--force-alert", action="store_true", help="Send fake alerts")
    parser.add_argument("--scrape", metavar="SITE_KEY", help="Scrape one site live")
    args = parser.parse_args()

    results: list[bool] = []

    if args.telegram:
        results.append(await test_telegram())
    elif args.force_alert:
        results.append(await test_force_alert())
    elif args.scrape:
        results.append(await test_scrape(args.scrape))
    else:
        # Run all tests
        results.append(test_database())
        results.append(await test_telegram())
        results.append(await test_force_alert())
        # Quick scrape on a lightweight site as a sanity check
        results.append(await test_scrape("pacvietnam"))

    print()
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"  🎉  All {total}/{total} tests passed!")
    else:
        print(f"  ⚠️   {passed}/{total} tests passed — see ❌ above for details")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
