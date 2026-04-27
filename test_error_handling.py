"""
Unit tests for error classification and the _scrape_one crash guard.

Tests the exact scenario that caused the GitHub Actions failure on 2026-04-27:
  aiohttp TimeoutError has str(e) == "" → str(e).splitlines()[0] → IndexError
  → crashed inside the except block → uncaught → process exit code 1.

Run with:
    python test_error_handling.py
"""

from __future__ import annotations

import asyncio
import socket
import sys
from unittest.mock import AsyncMock, MagicMock, patch

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from scrapers.base import ScraperError, is_transient_error
from playwright.async_api import TimeoutError as PwTimeout
import aiohttp

# ── colour helpers ────────────────────────────────────────────────────────────
GREEN = "\033[32m"
RED   = "\033[31m"
RESET = "\033[0m"
PASS  = f"{GREEN}PASS{RESET}"
FAIL  = f"{RED}FAIL{RESET}"

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    mark = PASS if condition else FAIL
    print(f"  [{mark}] {name}" + (f"  → {detail}" if detail else ""))


# ═════════════════════════════════════════════════════════════════════════════
# 1. is_transient_error — exhaustive type coverage
# ═════════════════════════════════════════════════════════════════════════════
print("\n── 1. is_transient_error() classifier ──────────────────────────────")

TRANSIENT_CASES = [
    ("asyncio.TimeoutError (empty msg)",    asyncio.TimeoutError()),
    ("asyncio.TimeoutError (with msg)",     asyncio.TimeoutError("connection timed out")),
    ("built-in TimeoutError",              TimeoutError()),
    ("Playwright TimeoutError",            PwTimeout("selector timeout")),
    ("ScraperError",                       ScraperError("no items parsed")),
    ("socket.gaierror",                    socket.gaierror(11001, "getaddrinfo failed")),
    ("socket.timeout",                     socket.timeout()),
    ("ConnectionError",                    ConnectionError("connection refused")),
    ("aiohttp.ServerTimeoutError",         aiohttp.ServerTimeoutError()),
    ("aiohttp.ClientConnectionError",      aiohttp.ClientConnectionError()),
    ("aiohttp.ClientPayloadError",         aiohttp.ClientPayloadError()),
    ("aiohttp 403 ClientResponseError",    aiohttp.ClientResponseError(
                                               MagicMock(), MagicMock(), status=403)),
    ("aiohttp 429 ClientResponseError",    aiohttp.ClientResponseError(
                                               MagicMock(), MagicMock(), status=429)),
    ("aiohttp 503 ClientResponseError",    aiohttp.ClientResponseError(
                                               MagicMock(), MagicMock(), status=503)),
    ("msg: 'net::err_connection_refused'", Exception("net::ERR_CONNECTION_REFUSED")),
    ("msg: 'timed out'",                   Exception("Request timed out after 90s")),
    ("msg: 'name_not_resolved'",           Exception("net::ERR_NAME_NOT_RESOLVED")),
]

NON_TRANSIENT_CASES = [
    ("AttributeError",                     AttributeError("'NoneType' has no attr 'text'")),
    ("KeyError",                           KeyError("title")),
    ("ValueError",                         ValueError("invalid date format")),
    ("aiohttp 200 ClientResponseError",    aiohttp.ClientResponseError(
                                               MagicMock(), MagicMock(), status=200)),
    ("aiohttp 404 ClientResponseError",    aiohttp.ClientResponseError(
                                               MagicMock(), MagicMock(), status=404)),
    ("TypeError",                          TypeError("Channel.getaddrinfo() takes 3 args")),
    ("IndexError",                         IndexError("list index out of range")),
    ("RuntimeError (generic)",             RuntimeError("unexpected state")),
]

for name, exc in TRANSIENT_CASES:
    check(f"transient: {name}", is_transient_error(exc))

for name, exc in NON_TRANSIENT_CASES:
    check(f"non-transient: {name}", not is_transient_error(exc))


# ═════════════════════════════════════════════════════════════════════════════
# 2. The crash guard — _scrape_one must NEVER raise even when str(e) is empty
# ═════════════════════════════════════════════════════════════════════════════
print("\n── 2. _scrape_one crash guard (the 2026-04-27 regression) ──────────")

# Dynamically import _scrape_one so we can inject mocks
import main as _main

SITE = {
    "key": "test_site",
    "company": "Test Co",
    "url": "https://example.com",
}

EMPTY_MSG_TRANSIENT = [
    ("TimeoutError (empty msg — exact GHA failure)",  TimeoutError()),
    ("asyncio.TimeoutError (empty msg)",              asyncio.TimeoutError()),
    ("aiohttp.ServerTimeoutError (empty msg)",        aiohttp.ServerTimeoutError()),
    ("socket.timeout (empty msg)",                    socket.timeout()),
    ("ConnectionError (empty msg)",                   ConnectionError()),
]

NONEMPTY_TRANSIENT = [
    ("TimeoutError with message",                     TimeoutError("read timeout")),
    ("ScraperError",                                  ScraperError("no items")),
    ("aiohttp 403",                                   aiohttp.ClientResponseError(
                                                          MagicMock(), MagicMock(), status=403)),
]

NON_TRANSIENT_RAISES = [
    ("AttributeError (non-transient)",                AttributeError("bad selector")),
    ("KeyError (non-transient)",                      KeyError("missing key")),
]


async def _run_scrape_one(exc: Exception) -> str:
    """Run _scrape_one with a scraper that raises `exc`. Return 'ok' or the error."""
    mock_scraper = MagicMock()
    mock_scraper.scrape = AsyncMock(side_effect=exc)
    mock_notifier = MagicMock()
    mock_notifier.send_admin = AsyncMock(return_value=True)

    try:
        await _main._scrape_one(mock_scraper, SITE, mock_notifier, seed_mode=False)
        return "ok"
    except Exception as e:
        return f"CRASHED: {type(e).__name__}: {e}"


for name, exc in EMPTY_MSG_TRANSIENT + NONEMPTY_TRANSIENT + NON_TRANSIENT_RAISES:
    result = asyncio.run(_run_scrape_one(exc))
    check(f"no crash: {name}", result == "ok", result if result != "ok" else "")


# ═════════════════════════════════════════════════════════════════════════════
# 3. Log message format — ensure the formatted string is always valid
# ═════════════════════════════════════════════════════════════════════════════
print("\n── 3. Log message format (no IndexError on empty str(e)) ───────────")

edge_cases = [
    ("empty string",        TimeoutError()),
    ("newline only",        Exception("\n")),
    ("multiline",           Exception("line1\nline2\nline3")),
    ("normal message",      Exception("read timeout after 60s")),
    ("unicode message",     Exception("kết nối bị từ chối")),
]

for name, exc in edge_cases:
    try:
        msg = (str(exc).splitlines() or [type(exc).__name__])[0][:200]
        check(f"format ok: {name}", True, repr(msg))
    except Exception as e:
        check(f"format ok: {name}", False, f"CRASHED: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\n{'═' * 60}")
print(f"  RESULT  {passed}/{total} passed", end="")
if failed:
    print(f"  —  {failed} FAILED:")
    for name, ok, detail in results:
        if not ok:
            print(f"    {RED}✗{RESET} {name}" + (f": {detail}" if detail else ""))
else:
    print(f"  {GREEN}— all good 🎉{RESET}")
print(f"{'═' * 60}\n")

sys.exit(0 if failed == 0 else 1)
