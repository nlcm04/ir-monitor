"""
Fetches each site with Playwright and prints a raw HTML snippet
of the first 3000 chars of the <body> so we can identify the correct selectors.

Usage:
    python diagnose.py phutai thienlong sasco vietjet acv
"""

from __future__ import annotations

import asyncio
import os
import sys

# Force UTF-8 output on Windows so Vietnamese characters don't crash print()
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

SITES_TO_CHECK = sys.argv[1:] or ["phutai", "thienlong", "sasco", "vietjet", "acv"]

from config import SITES

async def fetch(key: str) -> None:
    site = next((s for s in SITES if s["key"] == key), None)
    if not site:
        print(f"Unknown key: {key}")
        return

    print(f"\n{'='*60}")
    print(f"SITE: {key}  —  {site['url']}")
    print("="*60)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
            locale="vi-VN",
        )
        page = await ctx.new_page()
        try:
            await page.goto(site["url"], wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)
            html = await page.content()
            # Print a focused slice around common news keywords
            keywords = ["news", "article", "item", "list", "post", "tin", "pdf", "href"]
            for kw in keywords:
                idx = html.lower().find(kw)
                if idx != -1:
                    snippet = html[max(0, idx-200):idx+800]
                    print(f"\n--- First match for '{kw}' ---")
                    print(snippet)
                    break
            else:
                print(html[1000:3000])  # fallback: just print middle section
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await browser.close()

async def main():
    for key in SITES_TO_CHECK:
        await fetch(key)

asyncio.run(main())
