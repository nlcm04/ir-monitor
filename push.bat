@echo off
REM ============================================================================
REM  IR Monitor - push this folder's CODE to GitHub, safely.
REM  Repo: https://github.com/nlcm04/ir-monitor
REM
REM  WHY THIS IS NOT A PLAIN FORCE-PUSH:
REM  GitHub Actions runs the monitor on a schedule and saves the "already-seen
REM  articles" database (data\ir_monitor.db) back to the repo after every run.
REM  That server copy is the newest. If we overwrote it with the older copy on
REM  this PC, the bot would forget what it already sent and RE-SEND old articles
REM  to Telegram. So this script fetches the server's database first and keeps
REM  it, then replaces only the code/config files.
REM ============================================================================
cd /d "%~dp0"
echo Working in: %cd%
echo.

REM --- Make this folder a git repo the first time, and point it at the repo ---
if not exist ".git" git init
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/nlcm04/ir-monitor.git

REM --- Stage every file in this folder (your code + config changes) ---
git add -A
git commit -m "Update IR monitor" 2>nul

REM --- Preserve the server's live database so old alerts never re-send ---
echo.
echo Fetching the server's current database (so we do not overwrite it)...
git fetch origin main 2>nul
git checkout origin/main -- data/ir_monitor.db 2>nul
git add data/ir_monitor.db 2>nul
git commit --amend --no-edit 2>nul

echo.
echo ===== PUSHING to GitHub =====
git push origin main --force

echo.
echo ===== LOCAL commit  =====
git rev-parse main
echo ===== REMOTE commit (should match the LOCAL line above) =====
git ls-remote origin refs/heads/main
echo.
echo If the two hashes match, the push worked. GitHub Actions will pick up the
echo new code on its next scheduled run (every 1-2 hours).
echo If you saw "Authentication failed" or a login window, complete the GitHub
echo sign-in and run this file again.
echo.
pause
