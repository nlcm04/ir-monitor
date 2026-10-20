"""Investor-relations relevance filter.

The monitor's job is to surface genuine investor-relations disclosures —
financial statements, information disclosures (công bố thông tin), board
resolutions, AGM/EGM materials, dividends, insider/related-party share
transactions, governance and audit filings, share issuance, listing/regulator
notices — and to drop everything else: marketing, product catalogues, company
profiles, recruitment, events/PR, and FSC/forestry certification paperwork.

Two signals decide an item:

1.  BLOCK keywords — unambiguous non-IR content. If a title matches one, the
    item is dropped no matter what else it contains (so a "Catalogue …" or a
    forestry report never slips through, even on a filings feed).

2.  IR keywords — the vocabulary of real disclosures. On *news* feeds (company
    blogs that mix PR with the occasional filing) an item must match at least
    one of these to be kept. On dedicated IR / filings feeds the page itself is
    the IR section, so items are kept unless BLOCK-ed.

Matching is accent- and case-insensitive (``unidecode``) so "cổ tức" and "co
tuc" are the same, and typos in diacritics don't cause misses.
"""

from __future__ import annotations

from unidecode import unidecode

# Sites whose feed is a general company-news page (PR + marketing + the odd
# filing). Items from these are kept only when they look like a real disclosure.
NEWS_FEED_SITES = {"phutai", "theky"}

# --- Non-IR content: drop on sight, on every site ---------------------------
# Kept deliberately specific so a real filing is never caught by accident.
BLOCK_KEYWORDS = [
    # Marketing / product collateral
    "catalogue", "catalog", "brochure", "profile",
    "vien nen",          # wood-pellet product sheets ("Hồ Sơ Viên Nén Gỗ")
    "quang cao",         # advertising
    "khuyen mai", "uu dai",   # promotions
    # Press / events / HR / CSR
    "bai viet",          # reposted newspaper articles ("… – Bài viết …")
    "tuyen dung",        # recruitment
    "du lich cong ty",   # staff tours
    "hoi cho",           # trade fairs
    # FSC / forestry certification paperwork (operational, not IR)
    "quan ly rung", "chu rung", "hien trang rung", "chung chi rung",
    "da dang sinh hoc",  # biodiversity
    "tac dong moi truong", "tac dong xa hoi",  # env / social impact
    "tru luong",         # timber volume survey
    "giam sat noi bo nhom",   # FSC group internal monitoring
]

# --- IR vocabulary: a news-feed item needs at least one of these ------------
IR_KEYWORDS = [
    # Financial statements & results
    "bctc", "bao cao tai chinh", "financial statement",
    "bao cao thuong nien", "annual report",
    "giai trinh", "giai thich",            # explanation of results
    "ket qua kinh doanh", "sxkd", "kqkd", "business results",
    "kiem toan", "audit",                  # audit / audit-contract filings
    # Disclosures & resolutions / board actions
    "cong bo thong tin", "cbtt",
    "nghi quyet", "hdqt", "quyet dinh", "bien ban",
    "gop von", "von dieu le", "vdl", "cong ty con",   # material corporate actions
    "thanh lap cong ty", "chuyen nhuong",
    # General meetings
    "dai hoi", "dhdcd", "dhcd", "co dong", "tai lieu hop", "giay moi",
    "dkcc", "dang ky cuoi cung",           # record date
    # Capital / shares
    "co tuc", "dividend",
    "co phieu", "co phan", "giao dich", "phat hanh", "chao ban",
    "niem yet",                            # listing
    "vay von",                             # material borrowing disclosures
    # Governance / corporate changes
    "quan tri cong ty", "dieu le",
    "thay doi nhan su", "bo nhiem", "mien nhiem", "tu nhiem",
    "dkdn", "dkkd", "dang ky doanh nghiep", "dang ky kinh doanh",
    # Regulator / market references
    "so giao dich", "ubck", "ubcknn", "hnx", "hose", "sgdck",
    # IR comms
    "ban tin ir",
]


def _norm(text: str) -> str:
    return unidecode(text or "").lower()


def is_blocked(title: str) -> bool:
    hay = _norm(title)
    return any(kw in hay for kw in BLOCK_KEYWORDS)


def looks_like_ir(title: str) -> bool:
    hay = _norm(title)
    return any(kw in hay for kw in IR_KEYWORDS)


def is_relevant(title: str, site: dict) -> bool:
    """True if `title` is an investor-relations item worth alerting on.

    - Anything matching BLOCK_KEYWORDS is rejected outright.
    - On a general news feed, the title must also look like a real disclosure.
    - On a dedicated IR/filings feed, anything not blocked is kept.
    """
    if not title or len(title.strip()) < 5:
        return False
    if is_blocked(title):
        return False
    if site.get("key") in NEWS_FEED_SITES:
        return looks_like_ir(title)
    return True
