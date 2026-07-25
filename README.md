# IR Monitor — Vietnamese Equity IR/News → Telegram

Headless-browser monitor for 11 Vietnamese listed/unlisted company IR pages.
Scrapes with Playwright (handles JS-rendered sites and basic anti-bot checks),
stores seen articles in SQLite so alerts are never duplicated, and pushes
analyst-formatted notifications to Telegram with keyword flagging.

When a new financial-statement filing is detected, it also attaches a
year-over-year income-statement summary as a DOCX. These filings are commonly
scanned PDFs with no text layer, so the income statement is read via Tesseract
OCR (free, local) rather than plain text parsing — install Tesseract with the
Vietnamese language pack to enable it (see `.env.example`; the alert still
sends without it, the report attachment is just skipped).
