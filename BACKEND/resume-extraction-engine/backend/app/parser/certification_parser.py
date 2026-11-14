from __future__ import annotations

import re

from ..schemas.resume_schema import CertificationEntry
from .common import entry_meta
from .date_parser import find_dates
from .entries import list_items
from .url_parser import URL_RE, normalize_url

ISSUERS = ["Coursera", "Udemy", "AWS", "Amazon Web Services", "Google", "Microsoft", "IBM", "Oracle", "Cisco",
           "NPTEL", "Infosys", "Meta", "Udacity", "edX", "HackerRank", "Deloitte", "Simplilearn", "LinkedIn Learning",
           "Great Learning", "Scaler", "Kaggle", "DeepLearning.AI", "Stanford", "MIT", "Harvard", "Salesforce",
           "CompTIA", "PMI", "Red Hat", "Databricks", "Snowflake", "TCS", "Wipro", "Accenture", "Pluralsight",
           "freeCodeCamp", "Postman", "GitHub", "Nvidia", "NVIDIA", "Duke University", "Cognizant", "Forage",
           "Infosys Springboard", "Unstop", "Codecademy", "UpGrad", "upGrad", "Internshala", "NIIT", "SWAYAM"]
_ISS_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(i) for i in sorted(ISSUERS, key=len, reverse=True)) + r")(?![A-Za-z])")
_CRED_ID = re.compile(r"(?i)(?:credential\s*id|certificate\s*(?:id|no\.?|number)|cert(?:ification)?\s*(?:id|no\.?)|license\s*(?:no\.?|number)|\bID)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]{4,})")
_EXP = re.compile(r"(?i)(?:expires?|expiry|expiration|valid\s*(?:until|till|through|upto))\s*[:\-]?\s*")
_ISSUER_PAT = re.compile(r"(?i)\b(?:issued\s+by|offered\s+by|by|from|issuer|certified\s+by|organi[sz]ation)\s*[:\-]?\s+([A-Z][\w&.\- ]{1,50}?)(?=\s*(?:[|,;(\-–—]|\d{4}|$|credential|id\b))")


def parse_certifications(lines) -> list:
    out = []
    for text, ls in list_items(lines):
        urls = [normalize_url(m.group(0)) for m in URL_RE.finditer(text)]
        t = URL_RE.sub(" ", text)
        cred = None
        m = _CRED_ID.search(t)
        if m:
            cred = m.group(1)
            t = t[: m.start()] + " " + t[m.end():]
        exp = issue = None
        em = _EXP.search(t)
        if em:
            d = find_dates(t[em.end():])
            if d:
                exp = d[0][0]
                s, e = em.end() + d[0][2][0], em.end() + d[0][2][1]
                t = t[: em.start()] + " " + t[e:]
        dates = find_dates(t)
        if dates:
            issue = dates[0][0]
            for _, _, sp in reversed(dates):
                t = t[: sp[0]] + " " + t[sp[1]:]
        t = re.sub(r"(?i)\b(?:issued|completed|earned|date)\s*[:\-]?\s*", " ", t)
        issuer = None
        im = _ISSUER_PAT.search(t)
        if im:
            issuer = im.group(1).strip(" ,.-")
            t = t[: im.start()] + " " + t[im.end():]
        else:
            km = _ISS_RE.search(t)
            if km:
                issuer = km.group(1)
        parts = [p.strip(" ,|-–—:()") for p in re.split(r"\s+\|\s+|\s+[–—]\s+|\s+-\s+|\s*[•·]\s*|\s*\|\s*", t)]
        parts = [p for p in parts if p and len(re.findall(r"[A-Za-z]", p)) >= 3]
        name = parts[0] if parts else None
        if name and issuer and name.lower() == issuer.lower() and len(parts) > 1:
            name = parts[1]
        elif name and len(parts) > 1 and not im:
            cand = parts[1]
            if not re.search(r"\d", cand) and len(cand.split()) <= 6 and (_ISS_RE.search(cand) or cand[0].isupper()):
                issuer = cand
        if not name:
            continue
        score = 0.5 + 0.2 * bool(issuer) + 0.15 * bool(issue) + 0.15 * bool(cred or urls)
        out.append(CertificationEntry(
            name=name, issuer=issuer, issue_date=issue, expiration_date=exp, credential_id=cred,
            credential_url=urls[0] if urls else None, **entry_meta(ls, score)))
    return out
