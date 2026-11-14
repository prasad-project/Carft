from __future__ import annotations

import re

from ..schemas.resume_schema import PublicationEntry
from .common import entry_meta
from .date_parser import find_dates
from .entries import list_items
from .url_parser import URL_RE, normalize_url

_PUB = re.compile(r"(?i)\b(?:published\s+(?:in|at|by)|in\s+proceedings\s+of|journal\s+of|conference|IEEE|Springer|Elsevier|ACM|arXiv|Nature|Science|Wiley|Taylor\s*&\s*Francis)\b[^|,;]*")


def parse_publications(lines) -> list:
    out = []
    for text, ls in list_items(lines):
        urls = [normalize_url(m.group(0)) for m in URL_RE.finditer(text)]
        t = URL_RE.sub(" ", text)
        date = None
        ds = find_dates(t)
        if ds:
            date = ds[-1][0]
        title = None
        q = re.search(r"[\"“‘']([^\"”’']{8,200})[\"”’']", t)
        if q:
            title = q.group(1).strip(" ,.")
        pub = None
        m = _PUB.search(t)
        if m:
            pub = re.sub(r"(?i)^published\s+(?:in|at|by)\s+", "", m.group(0)).strip(" ,.-")
        if not title:
            seg = re.split(r"\s+\|\s+|\s+[–—]\s+|\s+-\s+|\.\s+(?=[A-Z])", t)[0]
            title = re.sub(r"\(?(?:19|20)\d{2}\)?", "", seg).strip(" ,.-:") or None
        if not title:
            continue
        desc = t.strip() if t.strip() != title else None
        score = 0.5 + 0.2 * bool(pub) + 0.15 * bool(date) + 0.15 * bool(urls)
        out.append(PublicationEntry(title=title, publisher=pub, date=date, url=urls[0] if urls else None,
                                    description=desc, **entry_meta(ls, score)))
    return out
