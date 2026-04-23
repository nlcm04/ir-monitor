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
        "wait_for": "article, .post, .elementor-post",
        "item": "article, .elementor-post",
        "title": "h2 a, h3 a, .elementor-post__title a",
        "link": "h2 a, h3 a, .elementor-post__title a",
        "date": "time, .elementor-post-date, .entry-date",
        "date_formats": ["%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d"],
        "base_url": "https://pacvietnam.vn",
        "scroll": False,
    },
    {
        "key": "theky",
        "company": "Thế Kỷ (CTCP Sách Thế Kỷ)",
        "url": "https://theky.vn/index.php/tin-tuc/",
        "wait_for": "h2.eael-post-list-title",
        "item": "h2.eael-post-list-title",
        "title": "a",
        "link": "a",
        "date": None,
        "date_formats": [],
        "base_url": "https://theky.vn",
        "scroll": False,
    },
    {
        "key": "ducgiangchem",
        "company": "Hóa chất Đức Giang (DGC)",
        "url": "https://ducgiangchem.vn/en/category/quan-he-co-dong/thong-bao/",
        "wait_for": "article, .post, .elementor-post, .entry",
        "item": "article, .elementor-post, .entry",
        "title": "h2 a, h3 a, .entry-title a, .elementor-post__title a",
        "link": "h2 a, h3 a, .entry-title a, .elementor-post__title a",
        "date": "time, .elementor-post-date, .entry-date, .posted-on",
        "date_formats": ["%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d"],
        "base_url": "https://ducgiangchem.vn",
        "scroll": False,
    },
    {
        "key": "phutai",
        "company": "Phú Tài (PTB)",
        "url": "https://phutai.com.vn/tin-tuc-va-su-kien/",
        "wait_for": "div.content-cate",
        "item": "div.content-cate",
        "title": "h3.title-cate",   # <h3> holds the text; img link has same href
        "link": "a.img-cate",        # use image link href — same URL, avoids empty-text issue
        "date": None,
        "date_formats": [],
        "base_url": "https://phutai.com.vn",
        "scroll": False,
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
        "wait_for": ".linkPdf",
        "item": ".linkPdf",
        "title": "a",
        "link": "a",
        # Date is embedded at the start of the link text: "17/04/2026: Article title"
        # Setting date to "a" lets _parse_date extract it via regex from the full text.
        "date": "a",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://ir.vietjetair.com",
        "scroll": True,
        # Strip "dd/mm/yyyy: " prefix from title so the headline is clean in Telegram
        "strip_date_prefix": True,
    },
    {
        "key": "dohaco",
        "company": "Dohaco Bến Tre (DHC)",
        "url": "https://dohacobentre.com.vn/quan-he-co-dong",
        # Page embeds an FPTS IR widget that loads news via AJAX — intercept the API response
        "intercept_url_contains": "gateway.fpts.com.vn/news/api/gateway/v1/mobile/list",
        "intercept_parser": "fpts",
        "base_url": "https://dohacobentre.com.vn",
    },
    {
        "key": "acv",
        "company": "ACV (Tổng Công ty Cảng HKVN)",
        "url": "https://acv.vn/vi/tin-tuc/thong-bao-co-dong",
        "wait_for": "a[href*='/vi/co-dong/']",
        # Each <a> is the item itself; title text ends with "HH:MM | DD/MM/YYYY"
        "item": "a[href*='/vi/co-dong/']",
        "title": None,
        "link": None,
        "date": None,
        "date_formats": ["%d/%m/%Y"],
        "base_url": "https://acv.vn",
        "scroll": True,
        "self_is_link": True,
        "strip_date_suffix": True,  # removes trailing "HH:MM | DD/MM/YYYY" from title
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
        "url": "https://tasecoairs.vn/thong-tin-co-dong.html",
        "wait_for": "a[href*='/thong-tin-co-dong/']",
        # Each item IS the <a> tag itself — no wrapper element
        "item": "a[href*='/thong-tin-co-dong/']",
        "title": None,   # use node text directly (see self_is_link handling in parser)
        "link": None,    # use node href directly
        "date": None,    # no date exposed on list page
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://tasecoairs.vn",
        "scroll": True,
        "self_is_link": True,  # tells parser the item node itself is the <a>
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

# Realistic User-Agent pool (rotated per-scrape)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]
