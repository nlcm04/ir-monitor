"""Find article links by filtering for long-text links that look like IR content."""
from __future__ import annotations
import asyncio, sys, re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGETS = {
    "thienlong": "https://thienlonggroup.com/quan-he-co-dong/tat-ca",
    "sasco":     "https://www.sasco.com.vn/shareholders",
}

async def fetch(key, url):
    print(f"\n{'='*60}\nSITE: {key}\n{'='*60}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36"
        )
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(4)
        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "lxml")
    for tag in soup.select("nav, script, style"):
        tag.decompose()

    # Print ALL links (no limit) to find articles
    links = soup.find_all("a", href=True)
    print(f"Total <a> tags: {len(links)}")
    print("\nAll links with text > 15 chars (skipping obvious nav):")
    skip = {"giới thiệu","trang chủ","liên hệ","tuyển dụng","english","tiếng việt","đăng nhập","đăng ký"}
    for a in links:
        text = a.get_text(" ", strip=True)
        href = a.get("href","")
        if len(text) > 15 and text.lower() not in skip and not href.startswith(("javascript","#","mailto","tel")):
            parent = a.parent
            gp = parent.parent if parent else None
            parent_info = f"{parent.name}.{' '.join(parent.get('class',[]))}" if parent else "?"
            gp_info = f"{gp.name}.{' '.join(gp.get('class',[]))}" if gp else "?"
            print(f"  GP:     <{gp_info}>")
            print(f"  PARENT: <{parent_info}>")
            print(f"  TEXT:   {text[:120]}")
            print(f"  HREF:   {href[:120]}")
            print()

async def main():
    for k, u in TARGETS.items():
        await fetch(k, u)

asyncio.run(main())
