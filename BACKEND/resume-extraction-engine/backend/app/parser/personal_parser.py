"""Name, headline and summary detection using position, shape and contextual evidence."""
from __future__ import annotations

import re
from typing import Optional

from ..utils.text_utils import join_wrapped, strip_bullet
from .contact_parser import CITIES, COUNTRIES, INDIAN_STATES
from .section_detector import heading_key
from .url_parser import EMAIL_RE, URL_RE

JOB_WORDS = (r"engineer|developer|analyst|scientist|manager|intern|designer|consultant|architect|programmer|"
             r"student|specialist|lead|director|administrator|researcher|officer|associate|executive|"
             r"tester|freelancer|fresher|graduate|enthusiast|professional|expert|technician|writer")
_JOB_RE = re.compile(rf"(?i)\b(?:{JOB_WORDS})s?\b")
_BAD_NAME = re.compile(
    r"(?i)\b(?:resume|curriculum|vitae|cv|profile|contact|summary|objective|education|experience|skills|projects|"
    r"address|email|e-mail|phone|mobile|linkedin|github|page|portfolio|declaration|references|certifications?)\b")
_PLACE_SET = {p.lower() for p in CITIES + COUNTRIES + INDIAN_STATES}
_TOKEN = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.'’\-]*$")
_HONORIFIC = re.compile(r"^(?:mr|mrs|ms|miss|dr|prof|er)\.?$", re.I)


def _name_ok(seg: str) -> Optional[list]:
    seg = seg.strip(" ,|•·-–—")
    if not seg or any(c.isdigit() for c in seg) or "@" in seg or ":" in seg or "/" in seg:
        return None
    if _BAD_NAME.search(seg) or _JOB_RE.search(seg) or heading_key(seg):
        return None
    toks = seg.split()
    while toks and _HONORIFIC.match(toks[0]):
        toks = toks[1:]
    if not 2 <= len(toks) <= 4 or not all(_TOKEN.match(t) for t in toks):
        return None
    if not all(t[0].isupper() for t in toks):
        return None
    if all(t.lower().strip(".,") in _PLACE_SET for t in toks) or seg.lower() in _PLACE_SET:
        return None
    return toks


def find_name(header_lines, email: Optional[str]):
    """Returns (full_name, first, last, line, conf) or None. Scores documented in docs/ARCHITECTURE.md:
    base 0.20 +0.30 first usable line +0.20 two/three tokens +0.15 title/upper case +0.25 token in email."""
    local = re.sub(r"[^a-z]", " ", (email or "").split("@")[0].lower()).split() if email else []
    best = None
    for idx, ln in enumerate(header_lines[:10]):
        for seg in re.split(r"\s+\|\s+|\s*[•·]\s*|\s+[–—-]\s+|,\s+", ln.text):
            toks = _name_ok(seg)
            if not toks:
                continue
            score = 0.20
            if idx == 0:
                score += 0.30
            if len(toks) in (2, 3):
                score += 0.20
            score += 0.15  # all tokens capitalised (enforced by _name_ok)
            joined_local = "".join(local)
            if any(len(t) >= 3 and (t.lower().strip(".") in local or t.lower().strip(".") in joined_local) for t in toks):
                score += 0.25
            score = round(min(score, 0.98), 2)
            if best is None or score > best[0]:
                name = " ".join(toks)
                if name.isupper():
                    name = name.title()
                parts = name.split()
                best = (score, name, parts[0], parts[-1], ln)
    if not best:
        return None
    return best[1], best[2], best[3], best[4], best[0]


def find_headline(header_lines, name_line, name: str):
    start = header_lines.index(name_line) if name_line in header_lines else 0
    for ln in header_lines[start:start + 5]:
        for seg in re.split(r"\s+\|\s+|\s*[•·]\s*|\s+[–—]\s+", ln.text):
            seg = seg.strip(" ,|")
            if not seg or seg == name or name in seg and len(seg) < len(name) + 3:
                continue
            if "@" in seg or URL_RE.search(seg) or re.search(r"\d{5,}", seg) or len(seg.split()) > 14:
                continue
            if _JOB_RE.search(seg) and not heading_key(seg) and not _BAD_NAME.search(seg):
                return seg, ln, 0.8
    return None


def find_summary(summary_lines) -> Optional[tuple]:
    parts = [strip_bullet(l.text)[0] for l in summary_lines]
    text = join_wrapped(parts)
    if len(text) < 20:
        return None
    return text, summary_lines[0], 0.9
