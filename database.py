"""SQLite state store for previously-seen articles.

De-duplication identity
-----------------------
Articles are keyed by a *fingerprint* that is deliberately robust to the file
host / CDN / query-string changing underneath us.  A document's download URL is
NOT a stable identity: Vietnamese IR back-ends routinely migrate storage (e.g.
Phú Tài moved every filing from ``api.phutai.com.vn/api/media/file/…`` to a
Cloudflare R2 bucket ``pub-….r2.dev/media/…`` in Oct 2026).  When the old
fingerprint hashed the raw URL, that single migration made all ~30 filings look
brand-new and re-flooded Telegram with months of backlog.

The fingerprint therefore hashes a *normalized identity*:
  - site_key          — so identical filenames on two sites never collide
  - stable path part  — for file links (``*.pdf`` etc.) just the URL-decoded
                        filename; for article pages the host-independent path.
                        The scheme/host/query are discarded, so a CDN move or a
                        ``?prefix=media`` tweak no longer changes identity.
  - title             — disambiguates two different files that happen to share a
                        filename, while staying constant across a host move.

Bumping the scheme is handled transparently by ``_migrate_fingerprints`` on
startup: existing rows are recomputed under the new scheme and duplicates
(old-host + new-host rows for the same document) are collapsed, keeping the
earliest ``first_seen``.  This means the fix itself does not trigger a flood.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

_DB_PATH = Path(__file__).parent / "data" / "ir_monitor.db"

# Current fingerprint scheme. Bump this (and nothing else) whenever the identity
# formula in `_norm_identity` changes, so `_migrate_fingerprints` re-keys the DB.
_FP_SCHEME = "v2"

# Extensions that mark a link as a downloadable document whose *filename* is its
# stable identity (host/CDN/query are irrelevant for these).
_DOC_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".csv", ".txt", ".rtf",
}


def _norm_identity(site_key: str, url: str, title: str) -> str:
    """Build the host-independent identity string for an item.

    File links collapse to ``<site>|file|<decoded-filename>|<title>``; article
    pages to ``<site>|page|<decoded-path>|<title>``.  In both cases the scheme,
    host and query string are dropped, so a storage/CDN migration or a changed
    query parameter no longer looks like a new article."""
    site = (site_key or "").strip().lower()
    t = (title or "").strip().lower()
    p = urlparse((url or "").strip())
    path = unquote(p.path)
    base = path.rsplit("/", 1)[-1]
    _, ext = os.path.splitext(base)

    if base and ext.lower() in _DOC_EXTS:
        return f"{site}|file|{base.strip().lower()}|{t}"

    norm_path = path.rstrip("/").lower()
    if not norm_path:
        # No meaningful path (identity lives in the query) — keep the query so
        # distinct items don't collapse into one.
        norm_path = f"{path.lower()}?{unquote(p.query).lower()}"
    return f"{site}|page|{norm_path}|{t}"


def _fingerprint(site_key: str, url: str, title: str) -> str:
    return hashlib.sha256(_norm_identity(site_key, url, title).encode("utf-8")).hexdigest()


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
        _migrate_fingerprints(con)


def _migrate_fingerprints(con: sqlite3.Connection) -> None:
    """Re-key existing rows to the current fingerprint scheme, collapsing any
    duplicates that result (e.g. the same filing recorded under an old host and
    a new host).  Idempotent: a `meta.fp_scheme` marker means it's a no-op.

    Crucially this runs *before* any scrape, so after the scheme bump the live
    scrape's fingerprints match the migrated rows and nothing re-alerts."""
    row = con.execute("SELECT value FROM meta WHERE key = 'fp_scheme'").fetchone()
    if row and row["value"] == _FP_SCHEME:
        return

    rows = con.execute(
        "SELECT fingerprint, site_key, company, title, url, published, first_seen FROM articles"
    ).fetchall()

    # new_fp -> chosen row (keep the earliest first_seen among collapsed dups)
    best: dict[str, dict] = {}
    for r in rows:
        nfp = _fingerprint(r["site_key"], r["url"], r["title"])
        cur = best.get(nfp)
        if cur is None or (r["first_seen"] or "") < (cur["first_seen"] or ""):
            best[nfp] = {
                "fingerprint": nfp,
                "site_key": r["site_key"],
                "company": r["company"],
                "title": r["title"],
                "url": r["url"],
                "published": r["published"],
                "first_seen": r["first_seen"],
            }

    con.execute("DELETE FROM articles")
    con.executemany(
        """
        INSERT OR REPLACE INTO articles
          (fingerprint, site_key, company, title, url, published, first_seen)
        VALUES (:fingerprint, :site_key, :company, :title, :url, :published, :first_seen)
        """,
        list(best.values()),
    )
    con.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES('fp_scheme', ?)", (_FP_SCHEME,)
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
            (f"seeded:{site_key}", datetime.now(timezone.utc).isoformat()),
        )


def filter_new(site_key: str, company: str, items: Iterable[dict]) -> list[dict]:
    """Return only items not already in the DB. Does NOT insert."""
    with _conn() as con:
        new_items: list[dict] = []
        seen_fps: set[str] = set()
        for it in items:
            fp = _fingerprint(site_key, it["url"], it["title"])
            # Guard against the same item appearing twice within one scrape
            # (e.g. two URLs for one filing) collapsing to the same identity.
            if fp in seen_fps:
                continue
            row = con.execute(
                "SELECT 1 FROM articles WHERE fingerprint = ?", (fp,)
            ).fetchone()
            if row is None:
                seen_fps.add(fp)
                it["fingerprint"] = fp
                it["site_key"] = site_key
                it["company"] = company
                new_items.append(it)
        return new_items


def record(items: Iterable[dict]) -> None:
    """Persist items that have been processed (alerted or seeded)."""
    now = datetime.now(timezone.utc).isoformat()
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
