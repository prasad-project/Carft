"""URL extraction and classification (LinkedIn, GitHub, Kaggle, ...)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")

KNOWN_HOSTS = (
    "linkedin.com", "github.com", "gitlab.com", "bitbucket.org", "kaggle.com", "hackerrank.com",
    "leetcode.com", "codeforces.com", "codechef.com", "medium.com", "twitter.com", "x.com",
    "behance.net", "dribbble.com", "stackoverflow.com", "huggingface.co", "geeksforgeeks.org",
    "linktr.ee", "dev.to", "youtube.com", "instagram.com", "facebook.com", "wellfound.com",
    "orcid.org", "researchgate.net", "scholar.google.com", "drive.google.com", "notion.site",
    "github.io", "vercel.app", "netlify.app", "herokuapp.com", "streamlit.app", "onrender.com",
    "web.app", "pages.dev",
)
_HOST_ALT = "|".join(re.escape(h) for h in sorted(KNOWN_HOSTS, key=len, reverse=True))
URL_RE = re.compile(
    rf"(?i)(?<![@\w/.\-])(?:(?:https?://|www\.)[^\s<>\"'|]+|(?:[a-z0-9\-]+\.)*(?:{_HOST_ALT})(?:/[^\s<>\"'|]*)?)"
)
PORTFOLIO_HOSTS = ("github.io", "vercel.app", "netlify.app", "pages.dev", "web.app", "onrender.com",
                   "herokuapp.com", "streamlit.app", "behance.net", "dribbble.com", "notion.site")


def normalize_url(u: str) -> str:
    u = u.strip().rstrip(".,;:)]}>'\"")
    if not re.match(r"(?i)^https?://", u):
        u = "https://" + u
    return u


def extract_urls(text: str) -> list:
    text = EMAIL_RE.sub(" ", text)
    return [normalize_url(m.group(0)) for m in URL_RE.finditer(text)]


def _host_path(u: str):
    p = urlparse(u)
    host = p.netloc.lower().removeprefix("www.")
    segs = [s for s in p.path.split("/") if s]
    return host, segs


def classify_url(u: str) -> str:
    """linkedin | github | github_repo | kaggle | leetcode | hackerrank | portfolio | other_social | website"""
    host, segs = _host_path(u)
    if host.endswith("linkedin.com"):
        return "linkedin" if segs and segs[0] in ("in", "pub") else "other_social"
    if host == "github.com":
        return "github" if len(segs) == 1 else ("github_repo" if len(segs) >= 2 else "other_social")
    if host.endswith("kaggle.com"):
        return "kaggle" if len(segs) >= 1 else "other_social"
    if host.endswith("leetcode.com"):
        return "leetcode" if segs else "other_social"
    if host.endswith("hackerrank.com"):
        return "hackerrank" if segs else "other_social"
    if any(host.endswith(h) for h in PORTFOLIO_HOSTS):
        return "portfolio"
    if any(host.endswith(h) for h in KNOWN_HOSTS):
        return "other_social"
    return "website"


def extract_social(header_lines, links, all_lines):
    """Returns (profiles dict, evidence dict key->(url, line)). Header first, then hyperlinks, then body."""
    cands = []  # (url, line|None)
    for l in header_lines:
        cands += [(u, l) for u in extract_urls(l.text)]
    cands += [(normalize_url(u), None) for u in links if u.lower().startswith(("http", "www"))]
    for l in all_lines:
        cands += [(u, l) for u in extract_urls(l.text)]
    prof, ev, other, website = {}, {}, [], None
    in_header = {id(l) for l in header_lines}
    for u, l in cands:
        kind = classify_url(u)
        if kind in ("linkedin", "github", "kaggle", "leetcode", "hackerrank", "portfolio"):
            key = kind
            if key not in prof:
                prof[key] = u
                ev[key] = (u, l)
        elif kind == "website" and website is None and (l is None or id(l) in in_header):
            website = u
            ev["website"] = (u, l)
        elif kind in ("other_social", "website") and u not in other and u != website:
            if l is None or id(l) in in_header:
                other.append(u)
    prof["other"] = [u for u in other if u not in prof.values()]
    prof["website"] = website
    return prof, ev
