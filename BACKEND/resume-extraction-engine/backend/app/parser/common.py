"""Shared helpers for all parsers: line construction, confidence maths, entry traceability."""
from __future__ import annotations

import re

from ..schemas.resume_schema import FieldTrace
from ..services.models import Line
from ..utils.text_utils import normalize_line

VERIFIED_THRESHOLD = 0.85


def lines_from_text(text: str, page: int = 1) -> list:
    """Build Line objects from plain text (used by tests and by callers that already have text)."""
    return [Line(normalize_line(t), page) for t in text.splitlines() if normalize_line(t)]


def cap_by_ocr(rule_conf: float, lines) -> float:
    """Confidence can never exceed the OCR engine's own confidence for the lines it came from."""
    confs = [l.ocr_conf for l in lines if l.ocr_conf is not None]
    if not confs:
        return round(rule_conf, 2)
    return round(min(rule_conf, (sum(confs) / len(confs)) / 100), 2)


def status_for(conf: float, validated: bool = True) -> str:
    return "verified" if validated and conf >= VERIFIED_THRESHOLD else "needs_review"


def entry_meta(lines, score: float) -> dict:
    """Traceability fields for a multi-field entry. `score` is a rule-completeness score in [0,1]."""
    conf = cap_by_ocr(min(score, 0.98), lines)
    raw = "\n".join(l.text for l in lines)
    return {
        "source_page": lines[0].page if lines else None,
        "source_text": raw[:800],
        "confidence": conf,
        "status": status_for(conf),
    }


class Collector:
    """Gathers per-field traces and warnings during parsing."""

    def __init__(self) -> None:
        self.traces: dict = {}
        self.warnings: list = []

    def trace(self, name: str, value, line, rule: str, rule_conf: float, validated: bool = True, source_text=None):
        lines = [line] if line is not None else []
        conf = cap_by_ocr(rule_conf, lines)
        self.traces[name] = FieldTrace(
            value=value,
            source_page=line.page if line is not None else None,
            source_text=(source_text if source_text is not None else (line.text if line is not None else None)),
            method="rule_based",
            rule=rule,
            confidence=conf,
            status=status_for(conf, validated),
        )


def remove_span(text: str, span) -> str:
    return (text[: span[0]] + " " + text[span[1]:]).strip()


def split_list(text: str) -> list:
    parts = re.split(r"\s*[,;|•·●▪]\s*|\s+/\s+", text)
    return [p.strip(" .") for p in parts if p.strip(" .")]
