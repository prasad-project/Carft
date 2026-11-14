"""Achievements / awards. One entry per list item."""
from __future__ import annotations

import re

from ..schemas.resume_schema import AchievementEntry
from .common import entry_meta
from .date_parser import find_dates
from .entries import list_items

_CATS = [("hackathon", r"hackathon|hack\b|codeathon"), ("competition", r"competition|contest|olympiad|challenge|cup\b"),
         ("ranking", r"\brank|\btop\s?\d+|percentile|\bAIR\b"), ("scholarship", r"scholarship|fellowship"),
         ("award", r"award|medal|prize|honou?r|winner|won\b|champion|runner|finalist|recogni[sz]ed")]
_ORG = re.compile(r"(?i)\b(?:by|at|from|organi[sz]ed by|conducted by|hosted by|issued by)\s+([A-Z][\w&.\- ]{2,50}?)(?=\s*(?:[|,;(\-–—]|\d{4}|$))")


def parse_achievements(lines) -> list:
    out = []
    for text, ls in list_items(lines):
        t = text
        date = None
        ds = find_dates(t)
        if ds:
            date = ds[-1][0]
            for _, _, sp in reversed(ds):
                t = t[: sp[0]] + " " + t[sp[1]:]
        t = re.sub(r"\(\s*\)", " ", t)
        org = None
        m = _ORG.search(t)
        if m:
            org = m.group(1).strip(" ,.-")
        segs = [s.strip(" ,|-–—:") for s in re.split(r"\s+\|\s+|\s+[–—]\s+|\s+-\s+|:\s+", t, maxsplit=1)]
        title = segs[0] if segs and segs[0] else None
        desc = segs[1] if len(segs) > 1 and segs[1] else None
        if not title:
            continue
        cat = next((c for c, p in _CATS if re.search(p, text, re.I)), None)
        score = 0.5 + 0.2 * bool(desc) + 0.15 * bool(date) + 0.15 * bool(org)
        out.append(AchievementEntry(title=title, description=desc, issuer=org, date=date, category=cat,
                                    **entry_meta(ls, score)))
    return out
