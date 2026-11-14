"""Education section parser: institution, degree, field, dates, CGPA/percentage/grade, coursework."""
from __future__ import annotations

import re
from typing import Optional

from ..schemas.resume_schema import EducationEntry
from ..utils.text_utils import strip_bullet
from .common import entry_meta, remove_span, split_list
from .date_parser import find_date_range, find_dates, year_of

_FULL = ["Bachelor of Technology", "Bachelor of Engineering", "Bachelor of Science", "Bachelor of Arts",
         "Bachelor of Commerce", "Bachelor of Business Administration", "Bachelor of Computer Applications",
         "Bachelor of Design", "Bachelor of Architecture", "Bachelor of Pharmacy", "Bachelor of Education",
         "Bachelor of Laws", "Master of Technology", "Master of Engineering", "Master of Science",
         "Master of Arts", "Master of Commerce", "Master of Business Administration",
         "Master of Computer Applications", "Master of Design", "Master of Education", "Master of Laws",
         "Doctor of Philosophy", "Post Graduate Diploma", "Postgraduate Diploma", "Diploma", "Associate Degree",
         "Bachelor's Degree", "Master's Degree", "Bachelors", "Masters", "Higher Secondary",
         "Senior Secondary", "Secondary School Certificate", "Intermediate", "High School", "Matriculation",
         r"Class\s+(?:XII|XI|X|12th|10th|12|10)", r"(?:12|10)th(?:\s+(?:Grade|Standard))?", "XII", "SSLC",
         "A-Levels", "GCSE"]
_ABBR_CI = [r"B\.?\s?Tech", r"M\.?\s?Tech", r"B\.?\s?Sc", r"M\.?\s?Sc", r"B\.?\s?Com", r"M\.?\s?Com",
            r"B\.?\s?Des", r"M\.?\s?Des", r"Ph\.?\s?D", r"B\.?B\.?A", r"M\.?B\.?A", r"B\.?C\.?A", r"M\.?C\.?A",
            "PGDM", r"B\.?Arch", r"B\.?Pharm", r"LL\.?B", r"LL\.?M"]
_ABBR_CS = [r"B\.E\.?", r"M\.E\.?", "BE", "ME", r"B\.A\.?", r"M\.A\.?", r"B\.S\.?", r"M\.S\.?", "BS", "MS",
            "BA", "MA", "SSC", "HSC", "CBSE", "ICSE", "ISC"]
_L, _R = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"
DEGREE_CI = re.compile(_L + "(?:" + "|".join(sorted(_FULL, key=len, reverse=True) + _ABBR_CI) + ")" + _R, re.I)
DEGREE_CS = re.compile(_L + "(?:" + "|".join(_ABBR_CS) + ")" + _R)
INSTITUTION_RE = re.compile(
    r"(?i:\b(?:University|College|Institute|Institution|School|Academy|Polytechnic|Vidyalaya|Vidyapeeth|"
    r"Mahavidyalaya|Institut|Universidad)\b)|\b(?:IIT|NIT|IIIT|BITS|IIM|VIT|SRM|NSIT|DTU|MIT|IISc|AIIMS|NITK)\b")
FIELD_WORDS = re.compile(
    r"(?i)\b(?:computer|science|engineering|information|technology|electronics|electrical|mechanical|civil|"
    r"mathematics|physics|chemistry|business|commerce|arts|data|software|artificial|intelligence|management|"
    r"finance|economics|biology|design|statistics|communication|accounting|marketing|applications|medical|"
    r"biotechnology|telecommunication|instrumentation|cyber|security|machine|learning|analytics|humanities)\b")
FIELD_ABBR = {"CSE", "ECE", "EEE", "IT", "CE", "AI", "ML", "DS", "AIML", "AIDS", "EE", "ME", "CS", "ISE", "MBA"}
CGPA_RE = re.compile(
    r"(?i)\b(?:CGPA|GPA|CPI|SGPA)\b\s*[:\-–]?\s*(\d{1,2}(?:\.\d{1,2})?)(?:\s*/\s*(\d{1,2}(?:\.\d+)?))?")
CGPA_BARE = re.compile(r"(?<![\d.])(\d(?:\.\d{1,2})?)\s*/\s*(10|4|5)(?:\.0)?(?!\d)")
PCT_RE = re.compile(r"(?i)(?:percentage|marks|score)\s*[:\-–]?\s*(\d{2,3}(?:\.\d{1,2})?)\s*%?|(\d{2,3}(?:\.\d{1,2})?)\s*%")
GRADE_RE = re.compile(
    r"(?i)\b(First Class(?: with Distinction)?|Distinction|Second Class|Honou?rs|Magna Cum Laude|Cum Laude|"
    r"Grade\s*[:\-]?\s*[A-F][+\-]?)\b")
COURSE_RE = re.compile(r"(?i)^(?:relevant\s+)?(?:course(?:work|s)?|subjects|modules)\s*[:\-–]\s*(.+)$")


def find_degree(text: str):
    """Returns (degree, field, span_of_degree_and_field) or None."""
    cands = [m for m in (DEGREE_CI.search(text), DEGREE_CS.search(text)) if m]
    if not cands:
        return None
    m = min(cands, key=lambda m: m.start())
    deg = re.sub(r"\s+", " ", m.group(0)).strip()
    rest = text[m.end():]
    field, end = None, m.end()
    fm = re.match(r"\s*\(\s*([A-Za-z&/ ,]{2,60}?)\s*\)", rest) or re.match(
        r"\s*(?:\bin\b|\bof\b|[-–—,:])\s*([A-Za-z][A-Za-z&/ ]{1,60}?)(?=\s*(?:$|[|(\d,]|\bfrom\b|\bat\b|\bCGPA\b|\bGPA\b|\bwith\b|[-–—]\s))",
        rest)
    if fm:
        cand = fm.group(1).strip()
        if FIELD_WORDS.search(cand) or cand.upper() in FIELD_ABBR:
            field, end = cand, m.end() + fm.end()
    return deg, field, (m.start(), end)


def _institution(text: str, degree_span) -> Optional[str]:
    t = text
    if degree_span:
        t = t[: degree_span[0]] + " | " + t[degree_span[1]:]
    for rx in (CGPA_RE, GRADE_RE):
        t = rx.sub(" | ", t)
    t = PCT_RE.sub(" | ", t)
    dr = find_date_range(t)
    if dr:
        t = remove_span(t, dr.span)
    for _, raw, span in reversed(find_dates(t)):
        t = t[: span[0]] + " " + t[span[1]:]
    segs = [s.strip(" ,|-–—:()") for s in re.split(r"\s+\|\s+|\s+[–—]\s+|\s+-\s+|\s*•\s*|\|", t)]
    for s in segs:
        if s and INSTITUTION_RE.search(s):
            s = re.sub(r"(?i)^(?:from|at)\s+", "", s)
            return s.strip(" ,")
    return None


def parse_education(lines) -> list:
    groups, cur = [], None

    def new_group(ln):
        nonlocal cur
        cur = [ln]
        groups.append(cur)

    state = {"inst": False, "deg": False}
    for ln in lines:
        text, bullet = strip_bullet(ln.text)
        if not text:
            continue
        if cur is None:
            new_group(ln)
            d, i = find_degree(text), bool(INSTITUTION_RE.search(text))
            state = {"inst": i, "deg": bool(d)}
            continue
        d, i = find_degree(text), bool(INSTITUTION_RE.search(text)) and not COURSE_RE.match(text)
        if not bullet and ((i and state["inst"]) or (d and state["deg"])):
            new_group(ln)
            state = {"inst": i, "deg": bool(d)}
        else:
            cur.append(ln)
            state["inst"] |= i
            state["deg"] |= bool(d)
    return [e for e in (_build(g) for g in groups) if e]


def _build(g) -> Optional[EducationEntry]:
    inst = deg = fld = grade = None
    dr = None
    cgpa = scale = pct = None
    courses: list = []
    dates_single = []
    for ln in g:
        t, _ = strip_bullet(ln.text)
        cm = COURSE_RE.match(t)
        if cm:
            courses += split_list(cm.group(1))
            continue
        d = find_degree(t)
        if d and not deg:
            deg, fld, dspan = d
        else:
            dspan = d[2] if d else None
        if not inst:
            inst = _institution(t, dspan)
        if not dr:
            dr = find_date_range(t)
            if not dr:
                dates_single += [x[0] for x in find_dates(t)]
        if cgpa is None:
            m = CGPA_RE.search(t) or CGPA_BARE.search(t)
            if m:
                cgpa = float(m.group(1))
                scale = float(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else (
                    10.0 if cgpa <= 10 else None)
                if cgpa > (scale or 10):
                    cgpa = scale = None
        if pct is None:
            m = PCT_RE.search(t)
            if m:
                v = float(m.group(1) or m.group(2))
                pct = v if 0 < v <= 100 else None
        if not grade:
            m = GRADE_RE.search(t)
            if m:
                grade = m.group(1)
    if not inst and not deg:
        return None
    if not inst and g:
        first, _ = strip_bullet(g[0].text)
        if not find_degree(first) and len(first.split()) <= 10 and first[0].isupper():
            cand = _institution(first, None) or None
            inst = cand
    start = end = None
    cur = False
    if dr:
        start, end, cur = dr.start, dr.end, dr.is_current
    elif dates_single:
        end = dates_single[-1]
    score = 0.3 * bool(inst) + 0.3 * bool(deg) + 0.2 * bool(start or end) + 0.1 * bool(fld) + 0.1 * bool(
        cgpa or pct or grade)
    return EducationEntry(
        institution=inst, degree=deg, field_of_study=fld, start_date=start, end_date=end, is_current=cur,
        graduation_year=year_of(end), cgpa=cgpa, cgpa_scale=scale, percentage=pct, grade=grade,
        relevant_coursework=courses, **entry_meta(g, score))
