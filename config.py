"""
Site configuration for the IR Monitor.

Each site is a dict describing:
  - key:        internal identifier (used as DB tag)
  - company:    display name shown in Telegram alerts
  - url:        page to scrape
  - wait_for:   a CSS selector Playwright waits for before parsing (anti-JS-race)
  - item:       CSS selector matching each news row/card
  - title:      relative selector inside `item` for the headline text
  - link:       relative selector inside `item` for the <a> (href extracted)
  - date:       relative selector inside `item` for the published date text
                (optional; None means the site doesn't expose a date on list view)
  - date_formats: list of strftime formats to try when parsing the date string
                  (fallback = raw string passed through)
  - base_url:   used to absolutize relative links
  - scroll:     whether to scroll the page to trigger lazy-loaded content
  - extra_headers: optional dict of HTTP headers

If a site changes its DOM, adjust the selectors here — no code edits needed.
"""

from __future__ import annotations

SITES = [
    {
        "key": "pacvietnam",
        "company": "PAC Việt Nam",
        "url": "https://pacvietnam.vn/category/tin-tuc/",
        # WordPress / Elementor — fully server-side rendered, no JS needed.
        "mode": "requests",
        "item": "article, .elementor-post",
        "title": "h2 a, h3 a, .elementor-post__title a",
        "link": "h2 a, h3 a, .elementor-post__title a",
        "date": "time, .elementor-post-date, .entry-date",
        "date_formats": ["%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d"],
        "base_url": "https://pacvietnam.vn",
    },
    {
        "key": "theky",
        "company": "Thế Kỷ (CTCP Sách Thế Kỷ)",
        "url": "https://theky.vn/index.php/tin-tuc/",
        # WordPress / Elementor — fully server-side rendered, no JS needed.
        "mode": "requests",
        "item": "h2.eael-post-list-title",
        "title": "a",
        "link": "a",
        "date": None,
        "date_formats": [],
        "base_url": "https://theky.vn",
    },
    {
        "key": "ducgiangchem",
        "company": "Hóa chất Đức Giang (DGC)",
        "url": "https://ducgiangchem.vn/en/category/quan-he-co-dong/thong-bao/",
        # WordPress — fully server-side rendered, no JS needed.
        "mode": "requests",
        "item": "article, .elementor-post, .entry",
        "title": "h2 a, h3 a, .entry-title a, .elementor-post__title a",
        "link": "h2 a, h3 a, .entry-title a, .elementor-post__title a",
        "date": "time, .elementor-post-date, .entry-date, .posted-on",
        "date_formats": ["%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d"],
        "base_url": "https://ducgiangchem.vn",
    },
    {
        "key": "phutai",
        "company": "Phú Tài (PTB)",
        "url": "https://phutai.com.vn/tin-tuc-va-su-kien/",
        # WordPress — fully server-side rendered, no JS needed.
        "mode": "requests",
        "item": "div.content-cate",
        "title": "h3.title-cate",   # <h3> holds the text; img link has same href
        "link": "a.img-cate",        # use image link href — same URL, avoids empty-text issue
        "date": None,
        "date_formats": [],
        "base_url": "https://phutai.com.vn",
    },
    {
        "key": "thienlong",
        "company": "Thiên Long Group (TLG)",
        "url": "https://thienlonggroup.com/quan-he-co-dong/tat-ca",
        "wait_for": "div.inner",
        "item": "div.inner",
        "title": "div.title a",
        "link": "div.title a",
        "date": None,
        "date_formats": [],
        "base_url": "https://thienlonggroup.com",
        "scroll": True,
    },
    {
        "key": "sasco",
        "company": "SASCO (SAS)",
        "url": "https://www.sasco.com.vn/shareholders",
        "wait_for": "a[href^='/shareholders/']",
        # Each article renders two <a> tags with identical hrefs:
        # 1) real title text, 2) full URL as text — filter_url_text_links handles dedup.
        "item": "a[href^='/shareholders/']",
        "title": None,
        "link": None,
        "date": None,
        "date_formats": [],
        "base_url": "https://www.sasco.com.vn",
        "scroll": True,
        "self_is_link": True,
        "filter_url_text_links": True,  # skip items whose title text looks like a URL
    },
    {
        "key": "vietjet",
        "company": "Vietjet Air (VJC)",
        "url": "https://ir.vietjetair.com/Home/Menu/thong-tin-khac",
        # Page is fully server-side rendered — .linkPdf items are in the initial HTML.
        # Previously used Playwright (403 on aiohttp from GHA IPs), but aiohttp now
        # works reliably with full Firefox headers. Playwright was getting anti-bot
        # interstitial pages on GHA US IPs, causing wait_for to time out with 0 items.
        "mode": "requests",
        "item": ".linkPdf",
        "title": "a",
        "link": "a",
        "date": "a",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://ir.vietjetair.com",
        "strip_date_prefix": True,
    },
    {
        "key": "dohaco",
        "company": "Dohaco Bến Tre (DHC)",
        # The dohacobentre.com.vn page embeds the FPTS IR widget as an <iframe>.
        # Rather than loading the parent page (which has slow CDN/analytics and
        # delays the iframe), we load the FPTS IR page directly — it's the same
        # source the iframe would load, just without the wrapper.
        "url": "https://ezir.fpts.com.vn/thongtindoanhnghiepclient/DHC",
        "intercept_url_contains": "gateway.fpts.com.vn/news/api/gateway/v1/mobile/list",
        "intercept_parser": "fpts",
        "intercept_wait_until": "networkidle",  # FPTS page is self-contained, networkidle is reliable
        "intercept_sleep": 5,
        "base_url": "https://dohacobentre.com.vn",
    },
    {
        "key": "acv",
        "company": "ACV (Tổng Công ty Cảng HKVN)",
        "url": "https://acv.vn/vi/tin-tuc/thong-bao-co-dong",
        # Next.js site — but links are included in the SSR HTML payload, so aiohttp
        # is sufficient. Playwright was timing out (page.goto > 90s) on GHA US IPs.
        "mode": "requests",
        "item": "a[href*='/vi/co-dong/']",
        "title": None,
        "link": None,
        "date": None,
        "date_formats": ["%d/%m/%Y"],
        "base_url": "https://acv.vn",
        "self_is_link": True,
        "strip_date_suffix": True,
    },
    {
        "key": "vietnamairlines",
        "company": "Vietnam Airlines (HVN)",
        "url": "https://www.vietnamairlines.com/vn/vi/vietnam-airlines/investor-relations/investor-news",
        # VNA uses Adobe AEM — news items are loaded via jcr:content JSON API calls
        "intercept_url_contains": "investor-news/jcr:content",
        "intercept_parser": "vna_jcr",
        "article_base_url": "https://www.vietnamairlines.com/vn/vi/vietnam-airlines/investor-relations/investor-news",
        "base_url": "https://www.vietnamairlines.com",
    },
    {
        "key": "tasecoairs",
        "company": "Taseco Airs (AST)",
        "url": "https://tasecoairs.vn/bao-cao-tai-chinh/bao-cao-tai-chinh-2026.html",
        # The .html extension and plain <a> link structure indicate SSR — no JS needed.
        # Playwright was timing out (90s) on GitHub Actions US IPs (server slow from US).
        # aiohttp bypasses the browser overhead and resolves in < 2s.
        # Point directly at the current year's report page so we get individual
        # quarterly/annual PDFs, not just the year-level index links.
        # Update URL each year: bao-cao-tai-chinh-20XX.html
        "mode": "requests",
        "item": "tr",
        "title": "td:first-child",
        "link": "a[href*='upload/userfiles']",  # only PDF upload links, skips footer junk
        "date": None,
        "date_formats": [],
        "base_url": "https://tasecoairs.vn",
    },
]

# Keywords that trigger the 🚨 flag on alerts. Matched case-insensitively
# and accent-insensitively against the headline.
FLAG_KEYWORDS = [
    ("cổ tức", "💰 DIVIDEND"),
    ("chia cổ tức", "💰 DIVIDEND"),
    ("lợi nhuận", "📈 EARNINGS"),
    ("kết quả kinh doanh", "📈 EARNINGS"),
    ("báo cáo tài chính", "📊 FINANCIALS"),
    ("báo cáo thường niên", "📊 ANNUAL REPORT"),
    ("đại hội", "🏛️ AGM/EGM"),
    ("đhđcđ", "🏛️ AGM/EGM"),
    ("từ nhiệm", "⚠️ RESIGNATION"),
    ("miễn nhiệm", "⚠️ RESIGNATION"),
    ("bổ nhiệm", "👤 APPOINTMENT"),
    ("phát hành", "🧾 ISSUANCE"),
    ("chào bán", "🧾 ISSUANCE"),
    ("giao dịch cổ phiếu", "🔁 INSIDER TRADE"),
    ("cổ đông lớn", "🐋 MAJOR HOLDER"),
    ("m&a", "🤝 M&A"),
    ("sáp nhập", "🤝 M&A"),
]

# ---------------------------------------------------------------------------
# Realistic User-Agent pool — rotated randomly per request.
# Heavily weighted toward Firefox (Gecko/Mozilla) since many Vietnamese IR
# sites are less aggressive about blocking Firefox versus headless Chrome.
# ---------------------------------------------------------------------------
USER_AGENTS = [
    # Firefox on Windows (most trusted by VN sites)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Firefox on Linux (matches GitHub Actions Ubuntu runner)
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Chrome on Windows (fallback)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# Full HTTP headers that accompany each Firefox UA — makes requests look like
# a real browser session (Content-Type negotiation, language, encoding, etc.)
FIREFOX_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.7,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}
