"""Work experience / internship parser."""
from __future__ import annotations

import re

from ..schemas.resume_schema import ExperienceEntry
from ..utils.text_utils import dedupe, strip_bullet
from .common import entry_meta, remove_span, split_list
from .contact_parser import CITIES, COUNTRIES, INDIAN_STATES
from .date_parser import find_date_range
from .entries import COMPANY_RE, JOB_RE, group_entries, is_achievement
from .skills_parser import find_skills

_PLACES = {p.lower() for p in CITIES + COUNTRIES + INDIAN_STATES}
_EMP = [(r"full[\s\-]?time", "Full-time"), (r"part[\s\-]?time", "Part-time"), (r"contract(?:or)?", "Contract"),
        (r"freelanc\w*", "Freelance"), (r"internship", "Internship"), (r"\bintern\b", "Internship"),
        (r"trainee", "Trainee"), (r"temporary", "Temporary"), (r"self[\s\-]?employed", "Self-employed"),
        (r"apprentice\w*", "Apprenticeship")]
_TECH_LINE = re.compile(
    r"(?i)^(?:technologies|technology|tech(?:nology)?\s*stack|tools|environment|stack|skills used|tools used)"
    r"(?:\s+used)?\s*[:\-–]\s*(.+)$")


def is_location(seg: str) -> bool:
    parts = [p.strip().lower() for p in re.split(r",|/", seg) if p.strip()]
    return bool(parts) and len(parts) <= 4 and all(p in _PLACES for p in parts)


def parse_header(header_lines):
    segs = []
    date = None
    for ln in header_lines:
        t = ln.text
        dr = find_date_range(t)
        if dr:
            date = date or dr
            t = remove_span(t, dr.span)
        t = re.sub(r"\(\s*\)|\[\s*\]", " ", t)
        for p in re.split(r"\s+\|\s+|\s+[–—]\s+|\s+-\s+|\s+@\s+|\s+at\s+|\s*[•·]\s*", t):
            p = p.strip(" ,|-–—")
            if p:
                segs.append(p)
    expanded = []
    for s in segs:
        if "," in s and not is_location(s):
            parts = [p.strip() for p in s.split(",") if p.strip()]
            merged = []
            for p in parts:
                if merged and re.fullmatch(r"(?i)(inc|llc|ltd|pvt|limited|corp|co)\.?", p):
                    merged[-1] += ", " + p
                else:
                    merged.append(p)
            if any(JOB_RE.search(p) for p in merged) or any(is_location(p) for p in merged):
                expanded += merged
                continue
        expanded.append(s)
    title = company = location = None
    left = []
    for s in expanded:
        if is_location(s) and not location:
            location = s
        elif JOB_RE.search(s) and not title and not (COMPANY_RE.search(s) and not re.search(
                r"(?i)\b(engineer|developer|analyst|intern)\b", s)):
            title = s
        elif not company:
            company = s
        else:
            left.append(s)
    return title, company, location, date, left


def _emp_type(text: str):
    for pat, name in _EMP:
        if re.search(pat, text, re.I):
            return name
    return None


def parse_experience(lines, default_type=None) -> list:
    out = []
    for e in group_entries(lines, max_header=3):
        title, company, location, dr, _ = parse_header(e.header)
        resp, ach, tech = [], [], []
        for text, bullet, ln in e.body:
            m = _TECH_LINE.match(text)
            if m:
                tech += split_list(m.group(1))
                continue
            (ach if is_achievement(text) else resp).append(text)
        body_text = " ".join(t for t, _, _ in e.body)
        for name, _ in find_skills(body_text, strict_context=True):
            tech.append(name)
        header_text = " ".join(l.text for l in e.header)
        if not title and not dr and not (company and COMPANY_RE.search(company)):
            continue
        emp = _emp_type(header_text) or default_type
        score = 0.3 * bool(title) + 0.3 * bool(company) + 0.25 * bool(dr) + 0.15 * bool(e.body)
        out.append(ExperienceEntry(
            job_title=title, company=company, location=location, employment_type=emp,
            start_date=dr.start if dr else None, end_date=dr.end if dr else None,
            is_current=bool(dr and dr.is_current), responsibilities=resp, achievements=ach,
            technologies=dedupe(tech), **entry_meta(e.lines, score)))
    return out
