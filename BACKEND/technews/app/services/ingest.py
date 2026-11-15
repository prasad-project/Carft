import logging
import secrets
from dataclasses import dataclass

import httpx
from sqlalchemy import select

from app.connectors import ALL_CONNECTORS, BY_KEY
from app.connectors.base import Connector, RawItem
from app.models import (Article, ArticleSource, Category, IngestionJob, IngestionLog, NewsSource, Tag)
from app.services import ai
from app.services.categorize import CATEGORIES, categorize, clean_tags
from app.services.dedupe import find_duplicate, normalize_title
from app.services.ranking import recompute_rankings
from app.util import aware, canonicalize_url as _canon, is_safe_url, slugify, strip_html, utcnow

log = logging.getLogger(__name__)
SOCIAL_KINDS = {"social"}


def seed_reference_data(db):
    for slug, name in CATEGORIES.items():
        if not db.scalar(select(Category).where(Category.slug == slug)):
            db.add(Category(slug=slug, name=name))
    for c in ALL_CONNECTORS:
        if not db.scalar(select(NewsSource).where(NewsSource.key == c.key)):
            db.add(NewsSource(key=c.key, name=c.name, kind=c.kind, access=c.access, notes=c.notes,
                              enabled=c.access == "free", quality_weight=c.authority / 100))
    db.commit()


@dataclass
class Counts:
    fetched: int = 0
    saved: int = 0
    duplicated: int = 0
    rejected: int = 0


def _tags(db, pairs):
    out = []
    for slug, name in pairs:
        t = db.scalar(select(Tag).where(Tag.slug == slug)) or Tag(slug=slug, name=name)
        out.append(t)
    return out


def process_item(db, raw: RawItem, conn: Connector, s, client=None) -> str:
    """Returns saved | duplicated | rejected | invalid."""
    title = strip_html(raw.title)[:500]
    if len(title) < 8 or not is_safe_url(raw.url):
        return "invalid"
    canonical = _canon(raw.url)
    now = utcnow()
    published = aware(raw.published_at) or now
    if published > now:
        published = now

    existing = db.scalar(select(ArticleSource).where(
        ArticleSource.source_key == raw.source_key, ArticleSource.external_id == raw.external_id))
    if existing:
        existing.metrics = {"engagement": raw.engagement}
        db.commit()
        return "duplicated"

    tnorm = normalize_title(title)
    dup, _why = find_duplicate(db, canonical, tnorm, published, s)
    if dup:
        _attach(db, dup, raw, conn, title, canonical)
        db.commit()
        return "duplicated"

    cat = categorize(title, raw.description, conn.topic_prior, conn.default_category)
    flags, summary, summary_ai = list(cat.flags), None, False
    category, relevance, tags = cat.category, cat.relevance, cat.tags + raw.tags
    if client is not None:
        extra = ai.enhance(s, client, title, raw.description)
        if extra:
            category = extra.get("category", category)
            if extra.get("relevance") is not None:
                relevance = extra["relevance"]
            tags += extra.get("tags", [])
            flags += extra.get("flags", [])
            summary, summary_ai = extra.get("summary"), bool(extra.get("summary"))

    art = Article(
        title=title, slug=f"{slugify(title)}-{secrets.token_hex(3)}", title_norm=tnorm,
        source_key=conn.key, source_name=conn.name, source_type=conn.kind,
        original_url=raw.url, canonical_url=canonical, author_name=raw.author, publisher_name=raw.publisher,
        thumbnail_url=raw.thumbnail if (s.show_third_party_thumbnails and is_safe_url(raw.thumbnail)) else None,
        description=raw.description, summary=summary, summary_is_ai=summary_ai, category=category,
        content_type=raw.content_type, relevance_score=relevance, published_at=published, fetched_at=now,
    )
    art.tags = _tags(db, clean_tags(tags))
    art.sources = [ArticleSource(source_key=conn.key, external_id=raw.external_id, url=raw.url,
                                 publisher_name=raw.publisher, metrics={"engagement": raw.engagement}, is_primary=True)]
    if relevance < s.min_relevance:
        art.status, art.review_reason = "rejected", f"auto: relevance {relevance} < {s.min_relevance}"
    elif flags or conn.kind in SOCIAL_KINDS or not s.auto_publish:
        art.status = "pending"
        art.review_reason = ", ".join(flags) or ("social source" if conn.kind in SOCIAL_KINDS else "auto-publish off")
    else:
        art.status = "published"
    db.add(art)
    db.commit()
    return "rejected" if art.status == "rejected" else "saved"


def _attach(db, art: Article, raw: RawItem, conn: Connector, title: str, canonical: str):
    """Record another discovery of the same story; promote the more authoritative source to primary."""
    cur = BY_KEY.get(art.source_key)
    promote = bool(cur and conn.authority > cur.authority)
    if promote:
        for src in art.sources:
            src.is_primary = False
    art.sources.append(ArticleSource(source_key=raw.source_key, external_id=raw.external_id, url=raw.url,
                                     publisher_name=raw.publisher, metrics={"engagement": raw.engagement},
                                     is_primary=promote))
    if "news.google.com" in art.original_url and "news.google.com" not in raw.url:
        art.original_url, art.canonical_url = raw.url, canonical      # direct publisher link beats a redirect
    if promote:
        art.source_key, art.source_name, art.source_type = conn.key, conn.name, conn.kind
        art.original_url, art.canonical_url, art.publisher_name = raw.url, canonical, raw.publisher
        art.content_type = raw.content_type
        if not art.is_edited:
            art.title = title


def run_ingestion(db_factory, s, *, job_id=None, source_keys=None, trigger="schedule", requested_by=None,
                  client=None, connectors=None) -> int:
    own_client = client is None
    client = client or httpx.Client(timeout=s.http_timeout, follow_redirects=True, headers={"User-Agent": s.user_agent})
    with db_factory() as db:
        seed_reference_data(db)
        job = db.get(IngestionJob, job_id) if job_id else None
        job = job or IngestionJob(trigger=trigger, requested_by=requested_by, source_keys=source_keys)
        job.status, job.started_at = "running", utcnow()
        db.add(job)
        db.commit()
        conns = connectors if connectors is not None else ALL_CONNECTORS
        rows = {r.key: r for r in db.scalars(select(NewsSource))}
        attempted = failed = 0
        for conn in conns:
            src = rows.get(conn.key)
            if source_keys and conn.key not in source_keys:
                continue
            if src is None or not src.enabled:
                continue
            log_row = IngestionLog(job_id=job.id, source_key=conn.key, status="running", started_at=utcnow())
            db.add(log_row)
            db.commit()                      # persist now so a later rollback can't lose the log row
            ok, reason = conn.availability(s)
            if not ok:
                src.status, src.status_reason = "unavailable", reason
                log_row.status, log_row.error, log_row.finished_at = "skipped", reason, utcnow()
                db.commit()
                continue
            attempted += 1
            c = Counts()
            try:
                items = conn.fetch(client, s)
                c.fetched = len(items)
                for it in items:
                    try:
                        res = process_item(db, it, conn, s, client)
                    except Exception:  # one bad record must not lose the rest
                        db.rollback()
                        log.exception("item_failed", extra={"source": conn.key, "external_id": it.external_id})
                        res = "invalid"
                    if res in ("saved", "duplicated", "rejected"):
                        setattr(c, res, getattr(c, res) + 1)
                    elif res == "invalid":
                        c.rejected += 1
                src.status, src.status_reason, src.last_success_at, src.last_error = "ok", None, utcnow(), None
                log_row.status = "success"
            except Exception as e:  # noqa: BLE001 - isolate connector failures
                db.rollback()
                failed += 1
                log.exception("connector_failed", extra={"source": conn.key})
                src = db.get(NewsSource, src.id)
                src.status, src.last_failure_at, src.last_error = "error", utcnow(), str(e)[:2000]
                src.status_reason = str(e)[:500]
                log_row = db.get(IngestionLog, log_row.id)
                log_row.status, log_row.error = "failed", str(e)[:2000]
            log_row.fetched, log_row.saved, log_row.duplicated, log_row.rejected = c.fetched, c.saved, c.duplicated, c.rejected
            log_row.finished_at = utcnow()
            db.commit()
            log.info("ingest_source_done", extra={"source": conn.key, **c.__dict__, "status": log_row.status})
        job = db.get(IngestionJob, job.id)
        job.status = "failed" if attempted and failed == attempted else "partial" if failed else "success"
        job.finished_at = utcnow()
        db.commit()
        recompute_rankings(db, s)
        jid = job.id
    if own_client:
        client.close()
    return jid
