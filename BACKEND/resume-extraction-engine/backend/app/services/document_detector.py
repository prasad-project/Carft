"""Document-type and per-page OCR-need detection."""
from __future__ import annotations

import re

from .models import PageContent


def guess_pdf_type(stats: list, min_chars: int) -> str:
    need = [c < min_chars or (cov > 0.6 and c < 4 * min_chars) for c, cov in stats]
    if all(need):
        return "scanned_pdf"
    if any(need):
        return "mixed_pdf"
    return "text_pdf"


def _alpha_ratio(text: str) -> float:
    compact = re.sub(r"\s", "", text)
    return (sum(ch.isalpha() for ch in compact) / len(compact)) if compact else 0.0


def mark_ocr_pages(pages: list, min_chars: int) -> list:
    """Flag pages whose embedded text is insufficient/garbled. Readable pages are never OCR'd."""
    need = []
    for p in pages:
        p.needs_ocr = (
            p.char_count < min_chars
            or _alpha_ratio(p.text) < 0.45
            or (p.image_coverage > 0.6 and p.char_count < 4 * min_chars)
        )
        if p.needs_ocr:
            need.append(p.page)
    return need


def final_pdf_type(pages: list) -> str:
    ocr = [p for p in pages if p.method == "ocr" or p.needs_ocr]
    if not ocr:
        return "text_pdf"
    return "scanned_pdf" if len(ocr) == len(pages) else "mixed_pdf"
