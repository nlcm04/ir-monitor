"""Check Cafef CBTT pages as alternative sources for all companies."""
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

TICKERS = {
    "vietjet":         "VJC",
    "vietnamairlines": "HVN",
    "sasco":           "SAS",
    "acv":             "ACV",
    "thienlong":       "TLG",
    "phutai":          "PTB",
    "ducgiangchem":    "DGC",
    "tasecoairs":      "AST",
    "dohaco":          "DHC",
    "pacvietnam":      "PAC",
    "theky":           "STK",
}

async def check(key, ticker):
    url = f"https://cafef.vn/du-lieu/cong-bo-thong-tin/{ticker}-3.chn"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36"
        )
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            html = await page.content()
        except Exception as e:
            print(f"{key:15} | ERROR: {e}")
            await browser.close()
            return
        await browser.close()

    soup = BeautifulSoup(html, "lxml")
    for tag in soup.select("script, style, nav, header, footer"):
        tag.decompose()

    links = [a for a in soup.find_all("a", href=True) if len(a.get_text(strip=True)) > 20]
    print(f"\n{key} ({ticker}) — {len(links)} links — {url}")
    for a in links[:5]:
        p = a.parent
        print(f"  [{p.name}.{' '.join(p.get('class',[])[:2])}]  {a.get_text(strip=True)[:80]}")
        print(f"  -> {a['href'][:90]}")

async def main():
    for key, ticker in TICKERS.items():
        await check(key, ticker)

asyncio.run(main())
