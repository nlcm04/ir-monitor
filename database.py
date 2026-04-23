"""SQLite state store for previously-seen articles."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable

_DB_PATH = Path(__file__).parent / "data" / "ir_monitor.db"


def _fingerprint(url: str, title: str) -> str:
    # Two sites sometimes publish the same URL twice with different titles, and
    # vice-versa. Hashing (url || title) makes the uniqueness test robust to both.
    h = hashlib.sha256()
    h.update(url.strip().lower().encode("utf-8"))
    h.update(b"|")
    h.update(title.strip().lower().encode("utf-8"))
    return h.hexdigest()


@contextmanager
def _conn():
    _DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                fingerprint TEXT PRIMARY KEY,
                site_key    TEXT NOT NULL,
                company     TEXT NOT NULL,
                title       TEXT NOT NULL,
                url         TEXT NOT NULL,
                published   TEXT,
                first_seen  TEXT NOT NULL
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_site ON articles(site_key)")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )


def is_seeded(site_key: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM meta WHERE key = ?", (f"seeded:{site_key}",)
        ).fetchone()
        return bool(row)


def mark_seeded(site_key: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            (f"seeded:{site_key}", datetime.utcnow().isoformat()),
        )


def filter_new(site_key: str, company: str, items: Iterable[dict]) -> list[dict]:
    """Return only items not already in the DB. Does NOT insert."""
    with _conn() as con:
        new_items: list[dict] = []
        for it in items:
            fp = _fingerprint(it["url"], it["title"])
            row = con.execute(
                "SELECT 1 FROM articles WHERE fingerprint = ?", (fp,)
            ).fetchone()
            if row is None:
                it["fingerprint"] = fp
                it["site_key"] = site_key
                it["company"] = company
                new_items.append(it)
        return new_items


def record(items: Iterable[dict]) -> None:
    """Persist items that have been processed (alerted or seeded)."""
    now = datetime.utcnow().isoformat()
    with _conn() as con:
        for it in items:
            con.execute(
                """
                INSERT OR IGNORE INTO articles
                  (fingerprint, site_key, company, title, url, published, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    it["fingerprint"],
                    it["site_key"],
                    it["company"],
                    it["title"],
                    it["url"],
                    it.get("published"),
                    now,
                ),
            )
