"""Date and date-range detection/normalisation. Output format: YYYY, YYYY-MM or YYYY-MM-DD."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]
MONTH_MAP = {n[:3]: i for i, n in enumerate(_NAMES, 1)}

MON = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
YEAR = r"(?:19|20)\d{2}"
_TOKENS = [
    rf"(?<!\d)\d{{1,2}}[/.\-]\d{{1,2}}[/.\-]{YEAR}(?!\d)",
    rf"(?<!\d)(?:0?[1-9]|1[0-2])[/.\-]{YEAR}(?!\d)",
    rf"\b{MON}\b\.?,?\s*(?:'\d{{2}}|{YEAR})(?!\d)",
    rf"(?<!\d){YEAR}[/\-.](?:0[1-9]|1[0-2])(?!\d)",
    rf"(?<![\d.]){YEAR}(?!\d)",
]
DATE_ANY = "(?:" + "|".join(_TOKENS) + ")"
PRESENT = r"(?:Present|Currently|Current|Now|Ongoing|Till\s+date|To\s+date|Today|Continuing|Till\s+now|Till\s+Present)"
_SEP = r"(?:\s*[-–—‑]\s*|\s+(?:to|until|till|through)\s+)"

RANGE_RE = re.compile(rf"(?P<s>{DATE_ANY}){_SEP}(?P<e>{DATE_ANY}|{PRESENT})", re.I)
MONTH_RANGE_RE = re.compile(
    rf"(?P<m1>{MON})\.?\s*(?:-|–|—|to)\s*(?P<m2>{MON})\.?,?\s*(?P<y>{YEAR})", re.I)
SHORT_RANGE_RE = re.compile(rf"(?P<s>{YEAR})\s*[-–—]\s*(?P<e>\d{{2}})(?!\d)")
SINGLE_RE = re.compile(DATE_ANY, re.I)
PRESENT_RE = re.compile(rf"^{PRESENT}$", re.I)


@dataclass
class DateRange:
    start: Optional[str]
    end: Optional[str]
    is_current: bool
    raw: str
    span: tuple


def normalize_date(tok: str) -> Optional[str]:
    t = tok.strip()
    m = re.fullmatch(rf"({MON})\.?,?\s*(?:'(\d{{2}})|({YEAR}))", t, re.I)
    if m:
        mon = MONTH_MAP[m.group(1).lower()[:3]]
        year = 2000 + int(m.group(2)) if m.group(2) else int(m.group(3))
        return f"{year}-{mon:02d}"
    m = re.fullmatch(rf"(\d{{1,2}})[/.\-](\d{{1,2}})[/.\-]({YEAR})", t)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if b <= 12 and a <= 31:
            return f"{y}-{b:02d}-{a:02d}"
        if a <= 12 and b <= 31:
            return f"{y}-{a:02d}-{b:02d}"
        return str(y)
    m = re.fullmatch(rf"(\d{{1,2}})[/.\-]({YEAR})", t)
    if m:
        return f"{int(m.group(2))}-{int(m.group(1)):02d}"
    m = re.fullmatch(rf"({YEAR})[/\-.](\d{{2}})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    if re.fullmatch(YEAR, t):
        return t
    return None


def find_date_range(text: str) -> Optional[DateRange]:
    m = MONTH_RANGE_RE.search(text)
    if m:
        y = int(m.group("y"))
        return DateRange(f"{y}-{MONTH_MAP[m.group('m1').lower()[:3]]:02d}",
                         f"{y}-{MONTH_MAP[m.group('m2').lower()[:3]]:02d}", False, m.group(0), m.span())
    m = RANGE_RE.search(text)
    if m:
        s = normalize_date(m.group("s"))
        e_raw = m.group("e")
        if PRESENT_RE.match(e_raw.strip()):
            return DateRange(s, None, True, m.group(0), m.span())
        e = normalize_date(e_raw)
        if s and e:
            return DateRange(s, e, False, m.group(0), m.span())
    m = SHORT_RANGE_RE.search(text)
    if m:
        s = m.group("s")
        e = s[:2] + m.group("e")
        if int(e) >= int(s):
            return DateRange(s, e, False, m.group(0), m.span())
    return None


def find_dates(text: str) -> list:
    """All single dates as (normalised, raw, span)."""
    out = []
    for m in SINGLE_RE.finditer(text):
        n = normalize_date(m.group(0))
        if n:
            out.append((n, m.group(0), m.span()))
    return out


def year_of(d: Optional[str]) -> Optional[int]:
    return int(d[:4]) if d else None
