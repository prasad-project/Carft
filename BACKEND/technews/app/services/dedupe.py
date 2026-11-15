import re
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher

from sqlalchemy import select

from app.models import Article
from app.util import aware, utcnow

STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "with", "at", "by", "is", "are", "its", "it"}


def normalize_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    tokens = [x.strip(".") for x in re.sub(r"[^a-z0-9.]+", " ", t).split()]
    return " ".join(x for x in tokens if x and x not in STOP)


def _nums(tokens: set[str]) -> set[str]:
    return {t for t in tokens if any(c.isdigit() for c in t)}


def similar(a: str, b: str, ratio_thr: float, jac_thr: float) -> bool:
    """Lexical similarity. Conservative on purpose: wrong merges are worse than missed ones.
    Titles that differ in any number (versions, years, amounts) are never merged."""
    ta, tb = set(a.split()), set(b.split())
    if len(ta) < 4 or len(tb) < 4 or _nums(ta) != _nums(tb):
        return False
    jac = len(ta & tb) / len(ta | tb)
    return jac >= jac_thr and SequenceMatcher(None, a, b).ratio() >= ratio_thr


def find_duplicate(db, canonical_url, title_norm, published_at, s) -> tuple[Article | None, str | None]:
    a = db.scalar(select(Article).where(Article.canonical_url == canonical_url))
    if a:
        return a, "canonical_url"
    center = aware(published_at) or utcnow()
    w = timedelta(hours=s.dedupe_window_hours)
    rows = db.execute(select(Article.id, Article.title_norm).where(
        Article.published_at >= center - w, Article.published_at <= center + w)).all()
    for aid, tn in rows:
        if tn == title_norm:
            return db.get(Article, aid), "title_exact"
    for aid, tn in rows:
        if similar(title_norm, tn, s.dedupe_title_ratio, s.dedupe_jaccard):
            return db.get(Article, aid), "title_similar"
    return None, None
