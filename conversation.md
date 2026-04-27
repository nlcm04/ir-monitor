# IR Monitor — Full Setup Conversation
Date: 2026-04-24

---

## User
Act as an expert Python developer and Web Scraping Architect. I am an Equity Analyst, and I need a robust, production-ready Python application to monitor the Investor Relations (IR) and News pages of my portfolio companies.

When new articles or announcements are published, the system must notify me via a Telegram Bot.

URLs to monitor:
1. https://pacvietnam.vn/category/tin-tuc/
2. https://theky.vn/index.php/tin-tuc/
3. https://ducgiangchem.vn/en/category/quan-he-co-dong/thong-bao/
4. https://phutai.com.vn/tin-tuc-va-su-kien/
5. https://thienlonggroup.com/quan-he-co-dong/tat-ca
6. https://www.sasco.com.vn/shareholders
7. https://ir.vietjetair.com/Home/Menu/thong-tin-khac
8. https://dohacobentre.com.vn/quan-he-co-dong
9. https://acv.vn/vi/tin-tuc/thong-bao-co-dong
10. https://www.vietnamairlines.com/vn/vi/vietnam-airlines/investor-relations/investor-news
11. https://tasecoairs.vn/thong-tin-co-dong.html

Requirements:
1. Use Playwright (async) for JS-rendered sites
2. Modular scraper with adjustable CSS selectors per site
3. Random delays and realistic User-Agent headers
4. SQLite to store previously scraped news (URL, Title, Date, Company Name)
5. Telegram notifications with HTML formatting including Company, Date, Headline, Link
6. Keyword tagging for: cổ tức, lợi nhuận, báo cáo tài chính, đại hội, từ nhiệm
7. Logging to file and console
8. Scheduler to check every 3 hours during business hours

## Assistant
Built the full project with these files:
- `main.py` — entrypoint + APScheduler
- `config.py` — per-site selectors, keywords, UA pool
- `database.py` — SQLite state store
- `notifier.py` — Telegram client + HTML formatting
- `logger.py` — console + rotating file log
- `scrapers/base.py` — Playwright scraper
- `requirements.txt`, `.env.example`, `README.md`, `.gitignore`

---

## User
How to run?

## Assistant
```bash
cd C:\Users\Windows\Downloads\Code\ir_monitor

# 1. One-time setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

# 2. Configure Telegram
copy .env.example .env
# Fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

# 3. Run
python main.py --site vietjet   # test one site
python main.py --once           # one full cycle
python main.py                  # start scheduler (every 3h, 07-19 ICT)
```

---

## User
Can you explain step by step how to run the code?

## Assistant
Step 1 — Open terminal in project folder
```bash
cd C:\Users\Windows\Downloads\Code\ir_monitor
```

Step 2 — Create virtual environment
```bash
python -m venv .venv
```

Step 3 — Activate virtual environment
```bash
.venv\Scripts\activate
```

Step 4 — Install dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Step 5 — Get Telegram credentials
- Talk to @BotFather → /newbot → copy Bot Token
- Message your bot once
- Visit https://api.telegram.org/bot<TOKEN>/getUpdates → copy chat id

Step 6 — Configure .env
```bash
copy .env.example .env
# Fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

Step 7 — Test one site
```bash
python main.py --site vietjet
```

Step 8 — Run one full cycle
```bash
python main.py --once
```

Step 9 — Start scheduler
```bash
python main.py
```

Troubleshooting table:
| Problem | Fix |
|---|---|
| TELEGRAM_BOT_TOKEN must be set | Fill in .env, run from ir_monitor/ folder |
| ⚠️ Scraper failed admin ping | Run HEADLESS=false python main.py --site <key>, tune selectors in config.py |
| Telegram message not arriving | Message the bot at least once first |
| playwright install fails | Run terminal as Administrator |

---

## User
What if Python was not found in step 2?

## Assistant
Option A — Install Python
- Download from python.org/downloads
- Run installer — CHECK "Add Python to PATH"
- Verify: `python --version`

Option B — Try alternate commands
```bash
python3 --version
py --version
py -m venv .venv   # use py instead of python
```

Option C — Install via winget
```bash
winget install Python.Python.3.12
```

---

## User
Since the website won't have new information in the next few days, how do I know that my system works? Can you test?

## Assistant
Created `test.py` with 4 tests:
1. Database — creates DB, inserts dummy article, verifies deduplication
2. Telegram connection — authenticates bot, sends silent ping
3. Forced alert — sends 2 fake articles to Telegram with keyword flags
4. Live scrape — scrapes PAC Việt Nam, prints first 5 articles to console

```bash
python test.py                  # run all tests
python test.py --telegram       # only test Telegram
python test.py --force-alert    # send fake alerts to Telegram
python test.py --scrape vietjet # scrape one site live
```

---

## User
What if I shut down my computer?

## Assistant
The scheduler stops when the PC sleeps/shuts down. Options:

| Approach | Cost | Runs while PC off? |
|---|---|---|
| Oracle Cloud Free VM | Free | Yes |
| Prevent sleep (power plan) | Free | Yes (wastes power) |
| Windows Task Scheduler | Free | Partial |
| GitHub Actions | Free | Yes |

Recommended: Oracle Cloud Free Tier or GitHub Actions.

For Linux VM (systemd service):
```ini
[Unit]
Description=IR Monitor
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/ir_monitor
ExecStart=/home/ubuntu/ir_monitor/.venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## User
Are there any free platforms that don't require a credit card?

## Assistant
Best option: GitHub Actions — free, no credit card, supports Playwright, cron schedule.

Created `.github/workflows/ir_monitor.yml` that:
- Runs on cron: 0 0,3,6,9,12 * * 1-5 (= 07,10,13,16,19 ICT weekdays)
- Installs Python + Playwright
- Writes .env from GitHub Secrets
- Runs `python main.py --once`
- Commits updated SQLite DB back to repo (state persistence)

Setup steps:
1. Create GitHub account (github.com, free, no card)
2. Create private repo named `ir-monitor`
3. Push code to GitHub
4. Create Personal Access Token (Settings → Developer settings → Tokens → repo scope)
5. Add secrets: GH_PAT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ADMIN_CHAT_ID
6. Test: Actions tab → IR Monitor → Run workflow

Free tier: 2,000 min/month. Each run ~10 min × 5/day × 22 days = ~1,100 min/month.

---

## User
Where to push code to GitHub? (step 3)

## Assistant
Run these in terminal inside the ir_monitor folder:
```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ir-monitor.git
git push -u origin main
```
When git push asks for login, use GitHub username + Personal Access Token as password.

If git not found: install from git-scm.com/download/win

---

## User
[Screenshot: "Author identity unknown" error]

## Assistant
Git doesn't know who you are. Run:
```bash
git config --global user.email "your@email.com"
git config --global user.name "Your Name"
```
Then retry: `git commit -m "initial commit"`

---

## User
What if I do not see my files on GitHub?

## Assistant
Check 1 — Did git push succeed?
```bash
git status
git log --oneline
```

Check 2 — Wrong repo URL
```bash
git remote -v
git remote set-url origin https://github.com/CORRECT_USERNAME/ir-monitor.git
git push -u origin main
```

Check 3 — Push never run
```bash
git push -u origin main
```

Check 4 — Wrong branch on GitHub (check main vs master dropdown)

---

## User
[Screenshot: "failed to push — fetch first" error]

## Assistant
Remote has files your local doesn't. Fix:
```bash
git pull origin main --allow-unrelated-histories
git push -u origin main
```
Or force push:
```bash
git push -u origin main --force
```

---

## User
[Merge conflict appeared in README.md] Then what's next?

## Assistant
Fixed the merge conflict in README.md (Windows line endings caused the edit to fail, rewrote the file cleanly).

```bash
git add README.md
git commit -m "fix merge conflict in README"
git push -u origin main
```

---

## User
[Screenshot: Node.js 20 deprecation warning in GitHub Actions]

## Assistant
Just a warning, not an error. Updated workflow to use newer action versions:
- `actions/checkout@v4` → `actions/checkout@v5`
- `actions/setup-python@v5` → `actions/setup-python@v6`

```bash
git add .github/workflows/ir_monitor.yml
git commit -m "fix: upgrade actions to Node.js 24 compatible versions"
git push
```

---

## User
How to test it can notify Telegram?

## Assistant
Option 1 — Trigger GitHub Actions manually:
Go to repo → Actions → IR Monitor → Run workflow

Option 2 — Test locally (faster, guaranteed notification):
```bash
cd C:\Users\Windows\Downloads\Code\ir_monitor
.venv\Scripts\activate
python test.py --force-alert
```
Sends 2 fake articles to Telegram immediately. If they appear, the full pipeline works.

---

## Project File Structure

```
ir_monitor/
├── .github/
│   └── workflows/
│       └── ir_monitor.yml    # GitHub Actions scheduler
├── scrapers/
│   ├── __init__.py
│   └── base.py               # Playwright scraper
├── data/
│   └── ir_monitor.db         # SQLite DB (auto-created)
├── logs/
│   └── ir_monitor.log        # rotating log (auto-created)
├── main.py                   # entrypoint + APScheduler
├── config.py                 # 11 sites config + keywords
├── database.py               # SQLite state store
├── notifier.py               # Telegram alerts
├── logger.py                 # logging setup
├── test.py                   # test suite
├── requirements.txt
├── .env.example
├── .env                      # your credentials (not committed)
├── .gitignore
└── README.md
```
