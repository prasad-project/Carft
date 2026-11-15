import html
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"fbclid", "gclid", "ref", "ref_src", "mc_cid", "mc_eid", "igshid", "cmpid", "source"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_safe_url(url: str | None) -> bool:
    if not url or len(url) > 2048:
        return False
    try:
        p = urlsplit(url.strip())
        host = p.hostname
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(host) and not p.username and not p.password


def canonicalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    q = sorted(
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
        if k.lower() not in TRACKING and not k.lower().startswith("utm_")
    )
    path = p.path.rstrip("/") or "/"
    return urlunsplit(("https", host + port, path, urlencode(q), ""))


def strip_html(s: str | None, limit: int | None = None) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"[\x00-\x08\x0b-\x1f]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s


def slugify(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80] or "story"


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return aware(datetime.fromisoformat(s.replace("Z", "+00:00")))
    except ValueError:
        return None
