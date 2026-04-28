"""
IR Monitor — entrypoint.

Usage:
    python main.py              # start the scheduler (runs forever)
    python main.py --once       # run a single scrape cycle and exit
    python main.py --site acv   # run only one site (for debugging selectors)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import signal
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

import database
from config import SITES
from logger import get_logger
from notifier import Notifier
from scrapers.base import PlaywrightScraper, ScraperError, is_transient_error

load_dotenv()
log = get_logger(__name__)


def _within_business_hours(tz: ZoneInfo) -> bool:
    start = int(os.getenv("BUSINESS_HOUR_START", "7"))
    end = int(os.getenv("BUSINESS_HOUR_END", "19"))
    now = datetime.now(tz)
    return start <= now.hour < end


async def _scrape_one(scraper: PlaywrightScraper, site: dict, notifier: Notifier,
                      seed_mode: bool) -> None:
    try:
        items = await scraper.scrape(site)
    except Exception as e:  # noqa: BLE001 — classify below, don't let one site kill the loop
        if is_transient_error(e):
            # Server-side or network hiccup (timeout, 403/429/5xx, DNS error,
            # connection reset, ScraperError after retries).  This is NOT a
            # bug in our code — the scheduler's next cycle will retry naturally.
            # Intentionally silent on Telegram to avoid alert fatigue; the
            # log line is still available for post-mortem debugging.
            log.warning(
                "[%s] transient failure — will retry next cycle (%s: %s)",
                site["key"], type(e).__name__,
                (str(e).splitlines() or [type(e).__name__])[0][:200],
            )
            return
        # Non-transient: this is a real bug in our code / config / selectors.
        # Alert the user so they can fix it.
        log.exception("[%s] non-transient error — admin alert sent", site["key"])
        await notifier.send_admin(
            f"⚠️ <b>Scraper bug</b> in <b>{site['company']}</b>\n"
            f"<code>{type(e).__name__}: {e}</code>\n"
            f"URL: {site['url']}"
        )
        return

    new_items = database.filter_new(site["key"], site["company"], items)
    log.info("[%s] %d items scraped, %d new", site["key"], len(items), len(new_items))

    if not new_items:
        return

    # First-run seeding: record everything silently so we don't flood the chat
    # with months of historical news the first time we see a site.
    first_run = not database.is_seeded(site["key"])
    if first_run and seed_mode:
        database.record(new_items)
        database.mark_seeded(site["key"])
        log.info("[%s] seeded %d existing items (no alerts)", site["key"], len(new_items))
        return

    sent = await notifier.send_many(new_items)
    database.record(new_items)  # record regardless — we tried to alert
    if not database.is_seeded(site["key"]):
        database.mark_seeded(site["key"])
    log.info("[%s] alerted %d/%d new items", site["key"], sent, len(new_items))


async def run_cycle(site_filter: str | None = None, force: bool = False) -> None:
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))
    if not force and site_filter is None and not _within_business_hours(tz):
        log.info("Outside business hours — skipping cycle")
        return

    seed_mode = os.getenv("SEED_ON_FIRST_RUN", "true").lower() == "true"
    notifier = Notifier()

    sites = [s for s in SITES if not site_filter or s["key"] == site_filter]
    if not sites:
        log.error("No matching site for filter=%r", site_filter)
        return

    log.info("=== Cycle start: %d sites ===", len(sites))
    async with PlaywrightScraper() as scraper:
        for site in sites:
            await _scrape_one(scraper, site, notifier, seed_mode)
            # Jittered delay between sites to look less bot-like.
            await asyncio.sleep(random.uniform(3.0, 8.0))
    log.info("=== Cycle complete ===")


async def _main_loop() -> None:
    database.init_db()
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))

    interval_h = max(1, int(os.getenv("RUN_EVERY_HOURS", "3")))
    start_h = int(os.getenv("BUSINESS_HOUR_START", "7"))
    end_h = int(os.getenv("BUSINESS_HOUR_END", "19"))

    # Fire at start_h, start_h+interval, ... within business window
    hours = ",".join(str(h) for h in range(start_h, end_h, interval_h))
    trigger = CronTrigger(hour=hours, minute=0, timezone=tz)

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(run_cycle, trigger=trigger, max_instances=1, coalesce=True,
                      misfire_grace_time=600)
    scheduler.start()
    log.info("Scheduler started — cron hours=%s TZ=%s", hours, tz)

    # Run one cycle immediately on startup so the user doesn't wait up to 3h.
    await run_cycle()

    stop = asyncio.Event()

    def _handle_stop(*_args):
        log.info("Shutdown signal received")
        stop.set()

    # SIGINT/SIGTERM handling (SIGTERM not available on Windows, hence the try).
    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is None:
            continue
        try:
            asyncio.get_event_loop().add_signal_handler(sig, _handle_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _handle_stop())

    await stop.wait()
    scheduler.shutdown(wait=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vietnamese IR/news monitor")
    parser.add_argument("--once", action="store_true", help="Run one cycle then exit")
    parser.add_argument("--site", help="Only scrape the given site key (see config.py)")
    args = parser.parse_args()

    database.init_db()

    if args.once or args.site:
        # force=True: the cron schedule controls timing on GHA, no need to
        # re-check business hours here. Delayed GHA runs (often +2-3h) would
        # otherwise be silently skipped if they land past the 19:00 ICT cutoff.
        asyncio.run(run_cycle(site_filter=args.site, force=True))
    else:
        try:
            asyncio.run(_main_loop())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
