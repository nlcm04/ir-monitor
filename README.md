# IR Monitor — Vietnamese Equity IR/News → Telegram

Headless-browser monitor for Vietnamese listed/unlisted company IR pages
(16 feeds across ~12 companies; see `config.py`).
Scrapes with Playwright (handles JS-rendered sites and basic anti-bot checks),
stores seen articles in SQLite so alerts are never duplicated, and pushes
analyst-formatted notifications to Telegram with keyword flagging.

When a new financial-statement filing is detected, it also attaches a
year-over-year income-statement summary as a DOCX. These filings are commonly
scanned PDFs with no text layer, so the income statement is read via Tesseract
OCR (free, local) rather than plain text parsing — install Tesseract with the
Vietnamese language pack to enable it (see `.env.example`; the alert still
sends without it, the report attachment is just skipped).

## How duplicates are prevented

Each article is de-duplicated by a **URL-robust fingerprint**: for file links
(`*.pdf`, `*.docx`, …) the identity is the decoded *filename* plus the title;
for article pages it is the host-independent *path* plus the title. The scheme,
host and query string are deliberately ignored.

This matters because Vietnamese IR back-ends move their files around. In Oct
2026 Phú Tài migrated every filing from `api.phutai.com.vn/api/media/file/…` to
a Cloudflare R2 bucket (`pub-….r2.dev/media/…`). The old fingerprint hashed the
raw URL, so that one migration made ~30 months-old filings look brand-new and
re-flooded Telegram. The filename-based fingerprint is immune to host/CDN moves.

Two further safety nets:

- **One-time DB migration** (`database.py`, scheme `v2`) re-keys existing rows on
  startup and collapses the old-host/new-host duplicate pairs, so deploying the
  fix does not itself cause a flood.
- **Flood guard** (`MAX_ALERTS_PER_CYCLE`, default 8): if an already-seeded site
  ever produces an abnormal burst of "new" items in one cycle (the signature of
  a future upstream change), only the newest few are alerted; the rest are
  recorded silently with a single admin heads-up.

## Investor-relations relevance filter

`relevance.py` keeps only genuine IR disclosures — financial statements, công bố
thông tin, board resolutions (NQ/QĐ HĐQT), ĐHĐCĐ materials, dividends, insider/
related-party share transactions, governance and audit filings, share issuance,
listing/regulator notices — and drops marketing, product catalogues, company
profiles, recruitment, events/PR, and FSC/forestry certification paperwork.
General company-news feeds (`phutai`, `theky`) must additionally match the IR
vocabulary to be alerted; dedicated IR/filings feeds are kept unless explicitly
blocked. Tune the keyword lists at the top of `relevance.py`.

## Deploying changes

The SQLite database (`data/ir_monitor.db`) is maintained on GitHub by the Actions
run after every cycle. To push code changes from this folder without reverting
that server-side database (which would re-send old articles), run **`push.bat`**:
it fetches and preserves the server's current database, then force-pushes only
the code/config. GitHub Actions picks up the new code on its next scheduled run.
