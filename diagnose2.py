"""Deep diagnostic — extracts all <a> links from each site to find article patterns."""

from __future__ import annotations
import asyncio, sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGETS = {
    "phutai":    "https://phutai.com.vn/tin-tuc-va-su-kien/",
    "thienlong": "https://thienlonggroup.com/quan-he-co-dong/tat-ca",
    "sasco":     "https://www.sasco.com.vn/shareholders",
    "acv":       "https://acv.vn/vi/tin-tuc/thong-bao-co-dong",
}

KEYS = sys.argv[1:] or list(TARGETS.keys())

async def fetch(key: str, url: str):
    print(f"\n{'='*60}\nSITE: {key} — {url}\n{'='*60}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
            locale="vi-VN",
        )
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(3)
        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "lxml")

    # Remove nav/header/footer noise
    for tag in soup.select("nav, header, footer, script, style, noscript"):
        tag.decompose()

    # Print all <a> tags with their parent tag + class
    links = soup.find_all("a", href=True)
    print(f"Total <a> tags found: {len(links)}\n")
    print("Sample article-looking links (first 20 with text > 10 chars):")
    shown = 0
    for a in links:
        text = a.get_text(" ", strip=True)
        href = a.get("href", "")
        if len(text) > 10 and not href.startswith(("#","javascript","mailto","tel")):
            parent = a.parent
            parent_info = f"{parent.name}.{' '.join(parent.get('class', []))}" if parent else "?"
            print(f"  PARENT: <{parent_info}>")
            print(f"  TEXT:   {text[:100]}")
            print(f"  HREF:   {href[:120]}")
            print()
            shown += 1
            if shown >= 20:
                break

async def main():
    for k in KEYS:
        if k in TARGETS:
            await fetch(k, TARGETS[k])

asyncio.run(main())
