"""
test_scrape.py — Live scrape test for all 11 portfolio companies.

Scrapes every site, reports success/failure, item count, timing, and a
2-article preview per site.  Does NOT touch the database or send Telegram
messages — safe to run at any time.

Usage
-----
    # Test all 11 sites:
    python test_scrape.py

    # Test specific sites by key:
    python test_scrape.py vietjet acv thienlong

    # Show only failures:
    python test_scrape.py --failures-only

Exit code: 0 if every tested site passes, 1 if any fail.
"""

from __future__ import annotations

import asyncio
import sys
import time

# Windows UTF-8 safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from config import SITES
from scrapers.base import PlaywrightScraper, ScraperError

# ── helpers ──────────────────────────────────────────────────────────────────

def _mode_label(site: dict) -> str:
    """Human-readable scrape mode for the site."""
    if site.get("intercept_url_contains"):
        return "api-intercept"
    if site.get("mode") == "requests":
        return "aiohttp"
    return "playwright"


def _bar(n: int, total: int = 40) -> str:
    filled = round(n / max(total, 1) * 20)
    return "█" * filled + "░" * (20 - filled)


# ── per-site test ─────────────────────────────────────────────────────────────

async def test_site(scraper: PlaywrightScraper, site: dict) -> dict:
    start = time.perf_counter()
    try:
        items = await scraper.scrape(site)
        elapsed = time.perf_counter() - start
        return {
            "key": site["key"],
            "company": site["company"],
            "mode": _mode_label(site),
            "status": "pass",
            "items": len(items),
            "elapsed": elapsed,
            "preview": items[:2],
            "error": None,
        }
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return {
            "key": site["key"],
            "company": site["company"],
            "mode": _mode_label(site),
            "status": "fail",
            "items": 0,
            "elapsed": elapsed,
            "preview": [],
            "error": str(exc),
        }


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    failures_only = "--failures-only" in flags

    # Filter sites by key if specific keys were given
    if args:
        valid_keys = {s["key"] for s in SITES}
        unknown = set(args) - valid_keys
        if unknown:
            print(f"Unknown site key(s): {', '.join(sorted(unknown))}")
            print(f"Valid keys: {', '.join(s['key'] for s in SITES)}")
            sys.exit(1)
        sites = [s for s in SITES if s["key"] in args]
    else:
        sites = list(SITES)

    print()
    print("=" * 68)
    print(f"  IR Monitor — scrape test  ({len(sites)} site{'s' if len(sites) != 1 else ''})")
    print("=" * 68)
    print()

    results: list[dict] = []

    async with PlaywrightScraper() as scraper:
        for i, site in enumerate(sites, 1):
            key = site["key"]
            company = site["company"]
            mode = _mode_label(site)
            print(f"[{i:2}/{len(sites)}] {company}")
            print(f"       key={key}  mode={mode}  url={site['url']}")
            print(f"       Testing...", end="", flush=True)

            result = await test_site(scraper, site)
            results.append(result)

            if result["status"] == "pass":
                bar = _bar(result["items"])
                print(
                    f"\r       ✅  {result['items']:2} items  {bar}  {result['elapsed']:.1f}s"
                )
                for item in result["preview"]:
                    title = (item.get("title") or "")[:70]
                    url = (item.get("url") or "")[:70]
                    pub = item.get("published") or "no date"
                    print(f"           [{pub}] {title}")
                    print(f"            → {url}")
            else:
                print(f"\r       ❌  FAILED  ({result['elapsed']:.1f}s)")
                # Print full error so the cause is obvious
                for line in result["error"].splitlines():
                    print(f"           {line}")

            print()

    # ── Summary ──────────────────────────────────────────────────────────────
    passed = [r for r in results if r["status"] == "pass"]
    failed = [r for r in results if r["status"] == "fail"]

    print("=" * 68)
    print(f"  SUMMARY  {len(passed)}/{len(results)} sites OK")
    print("=" * 68)

    if passed and not failures_only:
        print("\n✅ PASSING:")
        for r in passed:
            print(
                f"   {r['key']:20}  {r['company']:<35}  "
                f"{r['items']:2} items  {r['elapsed']:.1f}s  [{r['mode']}]"
            )

    if failed:
        print("\n❌ FAILING:")
        for r in failed:
            print(f"   {r['key']:20}  {r['company']}")
            # Show the first ~200 chars of the error — enough to diagnose
            snippet = r["error"][:200].replace("\n", " ")
            print(f"   → {snippet}")

    if not failed:
        print("\n  All sites are working correctly. 🎉")
    else:
        print(
            f"\n  {len(failed)} site(s) need attention — "
            "check selectors or network access."
        )

    print()
    sys.exit(0 if not failed else 1)


asyncio.run(main())
