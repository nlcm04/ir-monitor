"""
Generates a year-over-year income-statement DOCX for financial-statement PDFs.

Vietnamese financial statements (Circular 200/202) lay the income statement out
with two value columns side by side — "Kỳ này" (this period) and "Kỳ trước"
(same period last year) — so the YoY comparison is already in the source PDF;
no historical lookup is needed. The catch: in practice these PDFs are almost
always scanned images with no embedded text layer (confirmed against real
filings from several portfolio companies), so plain text extraction doesn't
work. Instead we render the first few pages to images and have Claude read the
table directly — far more robust than OCR on dense Vietnamese number tables.

Best-effort throughout: any failure (no API key, no PDF, nothing found) just
skips the report — it never blocks the normal Telegram alert.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Optional

import aiohttp
import pdfplumber
from unidecode import unidecode

from config import FIREFOX_HEADERS, FLAG_KEYWORDS, USER_AGENTS
from logger import get_logger

log = get_logger(__name__)

_OUTPUT_DIR = Path(__file__).parent / "reports"
_MAX_PAGES = 15
_MODEL = "claude-opus-5"

_INCOME_STATEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {
            "type": "boolean",
            "description": "true iff an income statement / statement of profit or loss table appears in these pages",
        },
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label_vn": {"type": "string", "description": "the line item's original Vietnamese label"},
                    "label_en": {"type": "string", "description": "short English translation"},
                    "current_period": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "prior_period": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                },
                "required": ["label_vn", "label_en", "current_period", "prior_period"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["found", "line_items"],
    "additionalProperties": False,
}

_EXTRACTION_PROMPT = (
    "These are scanned pages from a Vietnamese company's audited financial "
    "statement (báo cáo tài chính). Find the Income Statement / Statement of "
    "Profit or Loss (Báo cáo kết quả hoạt động kinh doanh) if it appears in "
    "these pages — a table with two value columns: 'Kỳ này' or similar "
    "(this period) and 'Kỳ trước' (same period last year). Extract every line "
    "item with both values as plain numbers in VND (no thousands separators; "
    "a value in parentheses is negative). If the statement isn't in these "
    "pages, set found=false and return an empty line_items array."
)

_HIGHLIGHT_LABELS = {"Net revenue", "Gross profit", "Operating profit", "Profit before tax", "Net profit after tax"}


def is_financial_statement(item: dict) -> bool:
    """True iff `item` is a PDF flagged with the Financials category."""
    url = (item.get("url") or "").lower()
    if ".pdf" not in url:
        return False
    hay = unidecode(item.get("title") or "").lower()
    return any(
        label == "Financials" and unidecode(kw).lower() in hay
        for kw, label in FLAG_KEYWORDS
    )


async def _download_pdf(url: str) -> bytes:
    from scrapers.base import PlaywrightScraper  # reuse the aiohttp connector builder

    import random

    connector = PlaywrightScraper._build_aiohttp_connector()
    headers = {**FIREFOX_HEADERS, "User-Agent": random.choice(USER_AGENTS)}
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(headers=headers, connector=connector, timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.read()


def _render_pages_to_base64(pdf_bytes: bytes, max_pages: int = _MAX_PAGES) -> list[str]:
    images: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            im = page.to_image(resolution=150).original
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            images.append(base64.standard_b64encode(buf.getvalue()).decode("utf-8"))
    return images


def _extract_income_statement(pdf_bytes: bytes) -> list[dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("ANTHROPIC_API_KEY not set — skipping financial report generation")
        return []

    images_b64 = _render_pages_to_base64(pdf_bytes)
    if not images_b64:
        return []

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}}
        for img in images_b64
    ]
    content.append({"type": "text", "text": _EXTRACTION_PROMPT})

    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        output_config={"format": {"type": "json_schema", "schema": _INCOME_STATEMENT_SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    if response.stop_reason == "refusal":
        log.warning("Claude declined the financial-statement extraction request")
        return []

    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)
    if not data.get("found"):
        return []

    return [
        {
            "label": it["label_en"],
            "label_vn": it["label_vn"],
            "current": it["current_period"],
            "prior": it["prior_period"],
        }
        for it in data.get("line_items", [])
    ]


def _fmt_number(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:,.0f}"


def _fmt_change(current: Optional[float], prior: Optional[float]) -> str:
    if current is None or prior is None or prior == 0:
        return "—"
    pct = (current - prior) / abs(prior) * 100
    return f"{'+' if pct >= 0 else ''}{pct:.1f}%"


def _safe_slug(text: str, maxlen: int = 60) -> str:
    slug = re.sub(r"[^\w\-]+", "_", unidecode(text)).strip("_")
    return slug[:maxlen] or "report"


def _build_docx(item: dict, rows: list[dict]) -> Path:
    from docx import Document
    from docx.shared import Pt

    _OUTPUT_DIR.mkdir(exist_ok=True)
    doc = Document()

    doc.add_heading(item["company"], level=1)
    doc.add_paragraph().add_run(item["title"]).italic = True

    meta = doc.add_paragraph()
    meta_run = meta.add_run(
        f"Published: {item.get('published') or '—'}\nSource: {item['url']}\n"
        "Figures extracted from the source PDF via AI vision — verify against the original before relying on them."
    )
    meta_run.font.size = Pt(9)

    doc.add_heading("Income Statement — Year over Year", level=2)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    headers = ["Line Item", "This Period (VND)", "Same Period Last Year (VND)", "YoY Change"]
    for cell, text in zip(table.rows[0].cells, headers):
        cell.text = text
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True

    for row in rows:
        cells = table.add_row().cells
        cells[0].text = row["label"]
        cells[1].text = _fmt_number(row["current"])
        cells[2].text = _fmt_number(row["prior"])
        cells[3].text = _fmt_change(row["current"], row["prior"])
        if row["label"] in _HIGHLIGHT_LABELS:
            for cell in cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True

    path = _OUTPUT_DIR / f"{item.get('site_key', 'report')}_{_safe_slug(item['title'])}.docx"
    doc.save(path)
    return path


async def maybe_generate_report(item: dict) -> Optional[Path]:
    """Best-effort: download + read + build a YoY income-statement DOCX for a
    financial-statement PDF. Returns the file path, or None if `item` isn't a
    financial-statement PDF, extraction found nothing, or any step failed."""
    if not is_financial_statement(item):
        return None

    try:
        pdf_bytes = await _download_pdf(item["url"])
    except Exception as e:
        log.warning("[%s] could not download PDF for report: %s", item.get("site_key"), e)
        return None

    try:
        rows = _extract_income_statement(pdf_bytes)
    except Exception as e:
        log.warning("[%s] income-statement extraction failed: %s", item.get("site_key"), e)
        return None

    if not rows:
        log.info("[%s] no income-statement rows found in %s — skipping DOCX", item.get("site_key"), item["url"])
        return None

    return _build_docx(item, rows)
