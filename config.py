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
        "wait_for": "article, .item-page, .items-leading, .blog",
        "item": "article, .items-leading > div, .items-row .item",
        "title": "h2 a, h3 a, .page-header a",
        "link": "h2 a, h3 a, .page-header a",
        "date": "time, .published, .create",
        "date_formats": ["%d/%m/%Y", "%Y-%m-%d"],
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
        "wait_for": ".news-item, article, .post, .blog-item, a",
        "item": ".news-item, article, .post, .blog-item",
        "title": "h2, h3, .title a, a",
        "link": "a",
        "date": ".date, time, .news-date",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://phutai.com.vn",
        "scroll": True,
    },
    {
        "key": "thienlong",
        "company": "Thiên Long Group (TLG)",
        "url": "https://thienlonggroup.com/quan-he-co-dong/tat-ca",
        "wait_for": ".news-item, article, .list-news li, .item, a[href*='quan-he-co-dong']",
        "item": ".news-item, .list-news li, article, .item",
        "title": "h2, h3, .title, a",
        "link": "a",
        "date": ".date, time, .news-date",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://thienlonggroup.com",
        "scroll": True,
    },
    {
        "key": "sasco",
        "company": "SASCO (SAS)",
        "url": "https://www.sasco.com.vn/shareholders",
        "wait_for": ".view-content, article, .node, .item-list, a",
        "item": ".views-row, article, .node, .item-list li",
        "title": "h2 a, h3 a, .title a, a",
        "link": "h2 a, h3 a, .title a, a",
        "date": ".date, time, .submitted, .field--name-field-date",
        "date_formats": ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"],
        "base_url": "https://www.sasco.com.vn",
        "scroll": True,
    },
    {
        "key": "vietjet",
        "company": "Vietjet Air (VJC)",
        "url": "https://ir.vietjetair.com/Home/Menu/thong-tin-khac",
        "wait_for": ".news-item, .list-news, article, a[href*='/Home/']",
        "item": ".news-item, .list-news li, article, .item, .row .col-md-12",
        "title": "h2, h3, h4, .title, a",
        "link": "a",
        "date": ".date, time, .news-date, .created",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://ir.vietjetair.com",
        "scroll": True,
    },
    {
        "key": "dohaco",
        "company": "Dohaco Bến Tre",
        "url": "https://dohacobentre.com.vn/quan-he-co-dong",
        "wait_for": "article, .post, .news-item, .item, a",
        "item": "article, .post, .news-item, .item, .col-md-4, .col-md-6",
        "title": "h2, h3, h4, .title, a",
        "link": "a",
        "date": ".date, time, .news-date",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://dohacobentre.com.vn",
        "scroll": True,
    },
    {
        "key": "acv",
        "company": "ACV (Tổng Công ty Cảng HKVN)",
        "url": "https://acv.vn/vi/tin-tuc/thong-bao-co-dong",
        "wait_for": "article, .news-item, .item, .list-news li, a",
        "item": "article, .news-item, .item, .list-news li",
        "title": "h2, h3, .title a, a",
        "link": "a",
        "date": ".date, time, .news-date, .time",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://acv.vn",
        "scroll": True,
    },
    {
        "key": "vietnamairlines",
        "company": "Vietnam Airlines (HVN)",
        "url": "https://www.vietnamairlines.com/vn/vi/vietnam-airlines/investor-relations/investor-news",
        "wait_for": ".news-item, .news-list, article, .item, a",
        "item": ".news-item, article, .item, .news-list li, .cmp-list__item",
        "title": "h2, h3, h4, .title, a",
        "link": "a",
        "date": ".date, time, .news-date, .cmp-list__item-date",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://www.vietnamairlines.com",
        "scroll": True,
    },
    {
        "key": "tasecoairs",
        "company": "Taseco Airs (AST)",
        "url": "https://tasecoairs.vn/thong-tin-co-dong.html",
        "wait_for": "article, .news-item, .item, .list-news li, a",
        "item": "article, .news-item, .item, .list-news li, .col-md-4, .col-md-6",
        "title": "h2, h3, h4, .title, a",
        "link": "a",
        "date": ".date, time, .news-date",
        "date_formats": ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"],
        "base_url": "https://tasecoairs.vn",
        "scroll": True,
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
