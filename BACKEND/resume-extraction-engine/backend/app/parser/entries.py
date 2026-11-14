"""Generic grouping of lines into (header, body) entries, plus list-item splitting for flat sections."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..services.models import Line
from ..utils.text_utils import is_bullet, strip_bullet, title_ratio
from .date_parser import find_date_range

JOB_WORDS = (r"engineer|developer|analyst|scientist|manager|intern|internship|trainee|consultant|architect|"
             r"designer|administrator|specialist|lead|director|officer|associate|executive|coordinator|assistant|"
             r"programmer|tester|qa|researcher|head|president|founder|co-founder|freelancer|technician|"
             r"supervisor|representative|strategist|writer|editor|teacher|professor|lecturer|tutor|mentor|"
             r"ambassador|sde|swe|devops|sre|apprentice|volunteer|member|secretary|captain|coder")
JOB_RE = re.compile(rf"(?i)\b(?:{JOB_WORDS})s?\b")
COMPANY_RE = re.compile(
    r"(?i)\b(?:inc|llc|ltd|limited|pvt|private|corp|corporation|co\.|company|technologies|technology|solutions|"
    r"systems|labs|software|services|consulting|group|industries|enterprises|bank|university|institute|studio|"
    r"ventures|infotech|innovations|digital|analytics|networks|foundation|ngo|agency|startup|club|society)\b")
_DATE_ONLY_REMAINDER = re.compile(r"[A-Za-z]{3,}")


@dataclass
class Entry:
    header: list = field(default_factory=list)
    body: list = field(default_factory=list)       # list of (text, is_bullet, Line)

    @property
    def lines(self) -> list:
        return self.header + [b[2] for b in self.body]


def is_header_like(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    words = t.split()
    dr = find_date_range(t)
    if dr:
        return True
    if len(words) > 14 or (t[-1] in ".;!?" and len(words) > 6):
        return False
    tr = title_ratio(t)
    if JOB_RE.search(t) and tr >= 0.5 and len(words) <= 12:
        return True
    if COMPANY_RE.search(t) and tr >= 0.5:
        return True
    if re.search(r"\s[|–—@]\s", t) and tr >= 0.5:
        return True
    return tr >= 0.7 and t[0].isupper() and t[-1] not in ".,;" and len(words) <= 8


def group_entries(lines, max_header: int = 3, header_pred=is_header_like) -> list:
    """Bullet lines are body. In header mode, header-like non-bullets extend the header (up to max_header).
    In body mode, a header-like non-bullet starting uppercase opens a new entry; lowercase starts are
    wrapped continuations."""
    entries, cur, mode = [], None, "header"
    for ln in lines:
        text, bullet = strip_bullet(ln.text)
        if not text:
            continue
        if cur is None:
            cur, mode = Entry(header=[Line(text, ln.page, ln.source, ln.ocr_conf)]), "header"
            entries.append(cur)
            continue
        if bullet:
            cur.body.append((text, True, ln))
            mode = "body"
            continue
        if mode == "header":
            if len(cur.header) < max_header and header_pred(text):
                cur.header.append(Line(text, ln.page, ln.source, ln.ocr_conf))
            else:
                cur.body.append((text, False, ln))
                mode = "body"
            continue
        # body mode
        if text[0].islower() and cur.body:
            t, b, l = cur.body[-1]
            cur.body[-1] = (t + " " + text, b, l)
        elif header_pred(text) and text[0].isupper():
            cur = Entry(header=[Line(text, ln.page, ln.source, ln.ocr_conf)])
            entries.append(cur)
            mode = "header"
        elif cur.body:
            t, b, l = cur.body[-1]
            if b and not t.rstrip().endswith((".", "!", "?")):
                cur.body[-1] = (t + " " + text, b, l)
            else:
                cur.body.append((text, False, ln))
        else:
            cur.body.append((text, False, ln))
    return entries


_CONT_RE = re.compile(r"(?i)^(?:credential|certificate|cert\.?|id\b|issued|expires?|expiry|valid|url|link|https?://|www\.)")


def list_items(lines) -> list:
    """Flat sections (certs, awards...). Returns list of (text, [Line,...])."""
    uses_bullets = any(is_bullet(l.text) for l in lines)
    items = []
    for ln in lines:
        text, bullet = strip_bullet(ln.text)
        if not text:
            continue
        if not items:
            items.append([text, [ln]])
        elif bullet:
            items.append([text, [ln]])
        elif text[0].islower() or _CONT_RE.match(text) or (uses_bullets and not bullet):
            items[-1][0] += " " + text
            items[-1][1].append(ln)
        else:
            items.append([text, [ln]])
    return [(t, ls) for t, ls in items]


QUANT_RE = re.compile(
    r"(?i)(?:\d[\d,.]*\s?(?:%|x\b|\+|k\b|m\b|million|billion|crore|lakh|users|customers|ms\b|hours|hrs|"
    r"requests|records|rows|clients|projects|members|participants)|\$\s?\d|₹\s?\d|\b(?:award|awarded|won|winner|"
    r"ranked|rank|finalist|recognized|recognised|selected|top\s?\d+|first place|runner)\b)")


def is_achievement(text: str) -> bool:
    return bool(QUANT_RE.search(text))
