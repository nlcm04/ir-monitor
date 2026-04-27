"""
Test alternative English-version URLs for failing company sites.
Simulates GitHub Actions by measuring load time + checking content.
"""
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Candidate English or alternative URLs from the SAME company domain
CANDIDATES = [
    # Vietjet
    ("vietjet_vi",  "https://ir.vietjetair.com/Home/Menu/thong-tin-khac"),
    ("vietjet_en",  "https://ir.vietjetair.com/Home/MenuEn/other-information"),
    ("vietjet_en2", "https://ir.vietjetair.com/Home/MenuEn/disclosure-information"),
    # ACV
    ("acv_vi",      "https://acv.vn/vi/tin-tuc/thong-bao-co-dong"),
    ("acv_en",      "https://acv.vn/en/news/shareholder-announcements"),
    ("acv_en2",     "https://acv.vn/en/investor-relations/shareholder-announcement"),
    # Thienlong
    ("thienlong_vi","https://thienlonggroup.com/quan-he-co-dong/tat-ca"),
    ("thienlong_en","https://thienlonggroup.com/en/investor-relations/all"),
    # SASCO
    ("sasco_vi",    "https://www.sasco.com.vn/shareholders"),
    ("sasco_en",    "https://www.sasco.com.vn/en/shareholders"),
]

async def check(key, url):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36"
        )
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
            status = resp.status if resp else "?"
            html = await page.content()
        except Exception as e:
            print(f"  {key:20} | FAILED: {str(e)[:60]}")
            await browser.close()
            return
        await browser.close()

    soup = BeautifulSoup(html, "lxml")
    for t in soup.select("script,style,nav,header,footer"):
        t.decompose()
    links = [a for a in soup.find_all("a", href=True) if len(a.get_text(strip=True)) > 20]
    print(f"  {key:20} | HTTP {status} | {len(links):3} links | {url}")
    for a in links[:3]:
        print(f"    -> {a.get_text(strip=True)[:70]}")

async def main():
    print("Testing alternative URLs...\n")
    for key, url in CANDIDATES:
        await check(key, url)
        await asyncio.sleep(1)

asyncio.run(main())
