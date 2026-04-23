<<<<<<< HEAD
# IR Monitor — Vietnamese Equity IR/News → Telegram

Headless-browser monitor for 11 Vietnamese listed/unlisted company IR pages.
Scrapes with Playwright (handles JS-rendered sites and basic anti-bot checks),
stores seen articles in SQLite so alerts are never duplicated, and pushes
analyst-formatted notifications to Telegram with keyword flagging.

## Project layout

```
ir_monitor/
├── main.py              # entrypoint + APScheduler
├── config.py            # per-site selectors, keywords, UA pool
├── database.py          # SQLite state store
├── notifier.py          # Telegram client + HTML formatting
├── logger.py            # console + rotating file log
├── scrapers/
│   └── base.py          # Playwright scraper (one class, selector-driven)
├── data/ir_monitor.db   # created on first run
├── logs/ir_monitor.log  # created on first run
├── requirements.txt
└── .env.example
```

## 1. Install

```bash
cd ir_monitor
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m playwright install chromium
```

Playwright's `install chromium` downloads a pinned Chromium build (~150 MB).
That's a one-off.

## 2. Configure Telegram

1. In Telegram, talk to **@BotFather** → `/newbot` → follow prompts. Copy the
   `BOT_TOKEN` it gives you.
2. Start a chat with your new bot (send it any message — this is required
   before it can message you).
3. Open in a browser:
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   Look for `"chat":{"id": <number>}` — that's your `CHAT_ID`.

Copy `.env.example` → `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=123456789
```

Optional: set `TELEGRAM_ADMIN_CHAT_ID` to a separate chat for scraper-failure
pings (defaults to your main chat, sent silently).

## 3. SQLite database

Created automatically on first run at `data/ir_monitor.db`. Schema:

| column       | type | notes                               |
| ------------ | ---- | ----------------------------------- |
| fingerprint  | TEXT | `sha256(url\|title)` — primary key  |
| site_key     | TEXT | e.g. `vietjet`, `acv`               |
| company      | TEXT | display name                        |
| title        | TEXT |                                     |
| url          | TEXT |                                     |
| published    | TEXT | normalized `YYYY-MM-DD` if parsable |
| first_seen   | TEXT | UTC ISO8601                         |

A `meta` table tracks which sites have been seeded. On the **first** scrape of
a site, all existing articles are recorded silently (controlled by
`SEED_ON_FIRST_RUN=true`) so you don't get flooded with months of back-catalog.

## 4. Run

```bash
# Test a single site (great for tuning selectors in config.py)
python main.py --site vietjet

# Run one full cycle across all sites, then exit
python main.py --once

# Start the scheduler (checks every 3h during business hours)
python main.py
```

Scheduler default: cron at `hour=7,10,13,16` Asia/Ho_Chi_Minh (configurable via
`BUSINESS_HOUR_START`, `BUSINESS_HOUR_END`, `RUN_EVERY_HOURS`). One cycle runs
immediately at startup.

## 5. Alert format

```
🚨 💰 DIVIDEND · 🏛️ AGM/EGM
🏢 Vietjet Air (VJC)
📅 2026-04-20
📰 Thông báo chi trả cổ tức năm 2025 và họp ĐHĐCĐ thường niên
🔗 Open article
```

Keyword flags are defined in `config.py:FLAG_KEYWORDS`. Matching is case- and
accent-insensitive (via `unidecode`), so `Cổ Tức`, `co tuc`, and `cổ tức` all
trigger the same flag.

## 6. Adjusting a broken scraper

When a site redesigns, the admin chat gets a `⚠️ Scraper failed` ping.
Reproduce locally:

```bash
HEADLESS=false python main.py --site <key>
```

Watching the live browser + adjusting the selectors in `config.py` (`item`,
`title`, `link`, `date`, `wait_for`) is almost always enough — no code changes
needed. The scraper raises `ScraperError` if zero items parse, so a drift is
loud rather than silent.

## 7. Running as a service

- **Linux (systemd)**: create a unit that runs `python main.py` with
  `Restart=always` and `WorkingDirectory` pointing at the repo.
- **Windows**: use Task Scheduler "At startup" → run `python.exe main.py`, or
  run under NSSM as a service.
- **Docker**: Playwright ships an official image
  (`mcr.microsoft.com/playwright/python:v1.48.0-jammy`) that has Chromium +
  fonts preinstalled — just `COPY` your code in and `CMD ["python","main.py"]`.

## 8. Rate-limiting & politeness

- Random 3–8s delay between sites.
- Random 0.8–2.0s jitter after page load before reading DOM.
- 4 rotated User-Agents (desktop Chrome/Firefox/Safari).
- `navigator.webdriver` flag stripped.
- 1 Telegram message every ~1.2s (well under the 30/s cap).

If you scale up to dozens of sites, consider adding a persistent-cookies
option and splitting into multiple browser contexts per run.
=======
# ir-monitor
>>>>>>> ab43391403fb3e5649f01e5ffa6d28a5625227fe
