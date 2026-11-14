"""Project section parser."""
from __future__ import annotations

import re

from ..schemas.resume_schema import ProjectEntry
from ..utils.text_utils import dedupe, join_wrapped
from .common import entry_meta, remove_span, split_list
from .date_parser import find_date_range, find_dates
from .entries import group_entries, is_achievement, is_header_like
from .skills_parser import find_skills
from .url_parser import URL_RE, classify_url, normalize_url

_TECH_LINE = re.compile(
    r"(?i)^(?:technologies|technology|tech(?:nology)?\s*stack|tools|built with|stack|tools used|technologies used)"
    r"\s*[:\-–]\s*(.+)$")
_ROLE_LINE = re.compile(r"(?i)^role\s*[:\-–]\s*(.+)$")
_LINK_WORD = re.compile(r"(?i)\b(?:github|source code|live demo|demo|link|repo|repository|code)\b\s*[:\-–]?")


def _header_pred(text: str) -> bool:
    if _TECH_LINE.match(text) or _ROLE_LINE.match(text):
        return False
    return is_header_like(text)


def parse_projects(lines) -> list:
    out = []
    for e in group_entries(lines, max_header=1, header_pred=_header_pred):
        head = e.header[0].text
        urls = [normalize_url(m.group(0)) for m in URL_RE.finditer(head)]
        for _, _, ln in e.body:
            urls += [normalize_url(m.group(0)) for m in URL_RE.finditer(ln.text)]
        h = URL_RE.sub(" ", head)
        dr = find_date_range(h)
        start, end = (dr.start, dr.end) if dr else (None, None)
        if dr:
            h = remove_span(h, dr.span)
        else:
            singles = find_dates(h)
            if singles:
                start = singles[0][0]
                for _, _, sp in reversed(singles):
                    h = h[: sp[0]] + " " + h[sp[1]:]
        h = _LINK_WORD.sub(" ", h)
        tech_text = ""
        h = h.strip()
        mp = re.search(r"\(([^)]+)\)\s*$", h)
        if mp and find_skills(mp.group(1), strict_context=False):
            tech_text, h = mp.group(1), h[: mp.start()]
        parts = [p.strip(" ,|-–—:") for p in re.split(r"\s+\|\s+|\s+[–—]\s+|\s+-\s+|\s*[•·]\s*|\s*:\s+", h)]
        parts = [p for p in parts if p]
        name = parts[0] if parts else None
        tech: list = []
        for p in parts[1:]:
            if find_skills(p, strict_context=False):
                tech += split_list(p)
        if tech_text:
            tech += split_list(tech_text)
        desc_parts, bullets, ach, role = [], [], [], None
        for text, bullet, ln in e.body:
            m = _TECH_LINE.match(text)
            if m:
                tech += split_list(m.group(1))
                continue
            m = _ROLE_LINE.match(text)
            if m:
                role = m.group(1).strip()
                continue
            if URL_RE.fullmatch(text.strip()) or _LINK_WORD.fullmatch(text.strip()):
                continue
            if bullet:
                bullets.append(text)
                if is_achievement(text):
                    ach.append(text)
            else:
                desc_parts.append(text)
        body_text = " ".join(t for t, _, _ in e.body) + " " + " ".join(tech)
        for n, _ in find_skills(body_text, strict_context=True):
            tech.append(n)
        gh = next((u for u in urls if classify_url(u) in ("github_repo", "github")), None)
        other = next((u for u in urls if u != gh), None)
        if not name:
            continue
        score = 0.4 * bool(name) + 0.3 * bool(desc_parts or bullets) + 0.2 * bool(tech) + 0.1 * bool(urls)
        out.append(ProjectEntry(
            name=name, description=join_wrapped(desc_parts) or None, bullet_points=bullets,
            technologies=dedupe([t for t in tech if t]), url=other, github_url=gh,
            start_date=start, end_date=end, role=role,
            achievements=ach, **entry_meta(e.lines, score)))
    return out
