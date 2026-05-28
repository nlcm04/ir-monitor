# IR Monitor — Vietnamese Equity IR/News → Telegram

Headless-browser monitor for 11 Vietnamese listed/unlisted company IR pages.
Scrapes with Playwright (handles JS-rendered sites and basic anti-bot checks),
stores seen articles in SQLite so alerts are never duplicated, and pushes
analyst-formatted notifications to Telegram with keyword flagging.
