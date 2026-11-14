"""Layout-aware embedded-text extraction with PyMuPDF.

Lines are rebuilt from span geometry. Same-row fragments (e.g. title ........ date) are joined with
' | '. Two-column pages are detected by finding a vertical gutter that few lines cross, and are read
column by column (full-width lines such as the name banner split the page into bands).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf as fitz

from ..utils.text_utils import normalize_line
from .models import Line, PageContent


@dataclass
class _L:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def _page_lines(page: fitz.Page) -> list:
    out = []
    d = page.get_text("dict")
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            txt = "".join(sp["text"] for sp in ln.get("spans", []))
            if txt.strip():
                x0, y0, x1, y1 = ln["bbox"]
                out.append(_L(x0, y0, x1, y1, txt))
    return out


def _find_split(lines: list, width: float):
    if len(lines) < 8:
        return None
    best = None
    for pct in range(25, 76):
        sx = width * pct / 100
        cross = sum(1 for l in lines if l.x0 < sx - 1 and l.x1 > sx + 1)
        left = sum(1 for l in lines if l.x1 <= sx + 1)
        right = sum(1 for l in lines if l.x0 >= sx - 1)
        if cross / len(lines) > 0.2 or left < 0.2 * len(lines) or right < 0.2 * len(lines):
            continue
        score = cross - 0.001 * (left + right)
        if best is None or score < best[0]:
            best = (score, sx)
    return best[1] if best else None


def _rows(lines: list) -> list:
    """Group fragments on the same visual row and join them left-to-right."""
    rows, cur, cur_y = [], [], None
    for l in sorted(lines, key=lambda l: (round(l.y0, 1), l.x0)):
        h = max(l.y1 - l.y0, 1)
        if cur and abs(l.y0 - cur_y) < 0.5 * h:
            cur.append(l)
        else:
            if cur:
                rows.append(cur)
            cur, cur_y = [l], l.y0
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        r.sort(key=lambda l: l.x0)
        text = r[0].text.strip()
        for prev, nxt in zip(r, r[1:]):
            sep = " | " if nxt.x0 - prev.x1 > 18 else " "
            text += sep + nxt.text.strip()
        out.append(text)
    return out


def order_lines(lines: list, width: float) -> list:
    split = _find_split(lines, width)
    if split is None:
        return _rows(lines)
    out, left, right = [], [], []

    def flush():
        out.extend(_rows(left))
        out.extend(_rows(right))
        left.clear()
        right.clear()

    for l in sorted(lines, key=lambda l: (l.y0, l.x0)):
        if l.x0 < split - 1 and l.x1 > split + 1:
            flush()
            out.extend(_rows([l]))
        elif l.x1 <= split + 1:
            left.append(l)
        else:
            right.append(l)
    flush()
    return out


def quick_scan(path) -> list:
    """Cheap per-page stats used for document-type detection: (chars, image_coverage)."""
    stats = []
    with fitz.open(path) as doc:
        for page in doc:
            chars = len(re.sub(r"\s", "", page.get_text("text")))
            area = max(page.rect.width * page.rect.height, 1)
            cov = 0.0
            try:
                for info in page.get_image_info():
                    r = fitz.Rect(info["bbox"]) & page.rect
                    cov += max(r.width * r.height, 0)
            except Exception:
                pass
            stats.append((chars, min(cov / area, 1.0)))
    return stats


def extract_pdf(path):
    """Returns (pages, links, metadata)."""
    pages, links = [], []
    with fitz.open(path) as doc:
        meta = {k: v for k, v in (doc.metadata or {}).items() if v}
        for i, page in enumerate(doc, start=1):
            rows = order_lines(_page_lines(page), page.rect.width)
            lines = []
            for r in rows:
                t = normalize_line(r)
                if t:
                    lines.append(Line(t, i, "embedded"))
            area = max(page.rect.width * page.rect.height, 1)
            cov = 0.0
            try:
                for info in page.get_image_info():
                    rr = fitz.Rect(info["bbox"]) & page.rect
                    cov += max(rr.width * rr.height, 0)
            except Exception:
                pass
            pc = PageContent(page=i, lines=lines, method="embedded", image_coverage=min(cov / area, 1.0))
            pc.char_count = len(re.sub(r"\s", "", pc.text))
            pages.append(pc)
            for lk in page.get_links():
                uri = lk.get("uri")
                if uri:
                    links.append(uri)
    return pages, links, meta
