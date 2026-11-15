from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.public import Page, serialize
from app.config import get_settings
from app.connectors import BY_KEY
from app.db import get_db
from app.models import (Article, ArticleSource, AuditLog, Category, IngestionJob, IngestionLog, NewsSource, Tag, User)
from app.schedule import next_runs
from app.security import require_admin
from app.services.categorize import clean_tags
from app.services.dedupe import normalize_title
from app.tasks import enqueue_ingestion
from app.util import canonicalize_url, is_safe_url, slugify, utcnow
import secrets

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def audit(db, user, action, target_type, target_id, detail=None):
    db.add(AuditLog(user_id=user.id, action=action, target_type=target_type, target_id=str(target_id), detail=detail))


def _get(db, aid) -> Article:
    a = db.get(Article, aid)
    if not a:
        raise HTTPException(404, "Article not found")
    return a


def _check_category(db, slug):
    if slug and not db.scalar(select(Category.id).where(Category.slug == slug)):
        raise HTTPException(422, f"Unknown category '{slug}'")


@router.get("/news")
def list_articles(status: str | None = None, q: str | None = Query(None, max_length=100), source: str | None = None,
                  pg: Page = Depends(), db: Session = Depends(get_db)):
    stmt = select(Article)
    if status:
        stmt = stmt.where(Article.status == status)
    if source:
        stmt = stmt.where(Article.source_key == source)
    if q:
        stmt = stmt.where(Article.title.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Article.created_at.desc()).offset(pg.offset).limit(pg.size)).all()
    return {"data": [serialize(a) | {"review_reason": a.review_reason} for a in rows],
            "meta": {"page": pg.page, "page_size": pg.size, "total": total}}


class ManualIn(BaseModel):
    title: str = Field(min_length=8, max_length=500)
    url: str
    summary: str | None = Field(None, max_length=1000)
    category: str | None = None
    content_type: str = Field("MANUAL_VIDEO", pattern="^(VERIFIED_NEWS|DEVELOPER_DISCOVERY|RESEARCH_UPDATE|PRODUCT_RELEASE|COMMUNITY_DISCUSSION|MANUAL_VIDEO)$")
    publisher_name: str | None = Field(None, max_length=200)
    thumbnail_url: str | None = None
    tags: list[str] = []
    publish: bool = False


@router.post("/news", status_code=201)
def create_manual(body: ManualIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if not is_safe_url(body.url) or (body.thumbnail_url and not is_safe_url(body.thumbnail_url)):
        raise HTTPException(422, "URL must be a valid http(s) URL")
    _check_category(db, body.category)
    now = utcnow()
    a = Article(title=body.title, slug=f"{slugify(body.title)}-{secrets.token_hex(3)}", title_norm=normalize_title(body.title),
                source_key="manual", source_name="Editorial", source_type="manual", original_url=body.url,
                canonical_url=canonicalize_url(body.url), publisher_name=body.publisher_name, summary=body.summary,
                category=body.category, content_type=body.content_type, thumbnail_url=body.thumbnail_url,
                relevance_score=1.0, status="published" if body.publish else "pending", is_edited=True,
                published_at=now, fetched_at=now)
    a.tags = [db.scalar(select(Tag).where(Tag.slug == s)) or Tag(slug=s, name=n) for s, n in clean_tags(body.tags)]
    db.add(a)
    db.flush()
    audit(db, admin, "create_article", "article", a.id)
    db.commit()
    return {"data": serialize(a)}


class PatchIn(BaseModel):
    title: str | None = Field(None, min_length=8, max_length=500)
    summary: str | None = Field(None, max_length=1000)
    description: str | None = Field(None, max_length=2000)
    category: str | None = None
    tags: list[str] | None = None
    is_featured: bool | None = None
    is_trending: bool | None = None
    thumbnail_url: str | None = None


@router.patch("/news/{aid}")
def patch_article(aid: int, body: PatchIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    a = _get(db, aid)
    d = body.model_dump(exclude_unset=True)
    _check_category(db, d.get("category"))
    if d.get("thumbnail_url") and not is_safe_url(d["thumbnail_url"]):
        raise HTTPException(422, "thumbnail_url must be a valid http(s) URL")
    if "tags" in d:
        a.tags = [db.scalar(select(Tag).where(Tag.slug == s)) or Tag(slug=s, name=n) for s, n in clean_tags(d.pop("tags") or [])]
    if "title" in d:
        a.title_norm = normalize_title(d["title"])
    if "summary" in d:
        a.summary_is_ai = False        # human-edited text is no longer AI text
    for k, v in d.items():
        setattr(a, k, v)
    a.is_edited = True
    audit(db, admin, "edit_article", "article", aid, {"fields": list(d)})
    db.commit()
    return {"data": serialize(a)}


def _set_status(db, admin, aid, status, reason=None):
    a = _get(db, aid)
    a.status, a.review_reason = status, reason
    audit(db, admin, f"{status}_article", "article", aid, {"reason": reason})
    db.commit()
    return {"data": serialize(a)}


class ReasonIn(BaseModel):
    reason: str | None = Field(None, max_length=500)


@router.post("/news/{aid}/publish")
def publish(aid: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _set_status(db, admin, aid, "published")


@router.post("/news/{aid}/reject")
def reject(aid: int, body: ReasonIn | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _set_status(db, admin, aid, "rejected", body.reason if body else None)


@router.post("/news/{aid}/archive")
def archive(aid: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _set_status(db, admin, aid, "archived")


@router.delete("/news/{aid}", status_code=204)
def delete_article(aid: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    a = _get(db, aid)
    audit(db, admin, "delete_article", "article", aid, {"title": a.title})
    db.delete(a)
    db.commit()


# ---- sources -------------------------------------------------------------------------------------------
def _src(r: NewsSource):
    c = BY_KEY.get(r.key)
    s = get_settings()
    ok, why = c.availability(s) if c else (False, "connector missing")
    return {"id": r.id, "key": r.key, "name": r.name, "kind": r.kind, "access": r.access, "enabled": r.enabled,
            "quality_weight": r.quality_weight, "status": r.status, "status_reason": r.status_reason or (None if ok else why),
            "available_now": ok, "notes": r.notes, "last_success_at": r.last_success_at,
            "last_failure_at": r.last_failure_at, "last_error": r.last_error}


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    return {"data": [_src(r) for r in db.scalars(select(NewsSource).order_by(NewsSource.id))]}


class SourcePatch(BaseModel):
    enabled: bool | None = None
    quality_weight: float | None = Field(None, ge=0, le=1)


@router.patch("/sources/{sid}")
def patch_source(sid: int, body: SourcePatch, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    r = db.get(NewsSource, sid)
    if not r:
        raise HTTPException(404, "Source not found")
    d = body.model_dump(exclude_unset=True)
    for k, v in d.items():
        setattr(r, k, v)
    audit(db, admin, "edit_source", "source", sid, d)
    db.commit()
    return {"data": _src(r)}


def _queue(db, admin, keys):
    job = IngestionJob(trigger="manual", requested_by=admin.id, source_keys=keys, status="queued")
    db.add(job)
    db.flush()
    audit(db, admin, "trigger_ingestion", "ingestion", job.id, {"sources": keys})
    db.commit()
    enqueue_ingestion(job.id, keys)
    return {"data": {"job_id": job.id, "status": "queued"}}


@router.post("/sources/{sid}/fetch", status_code=202)
def fetch_source(sid: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    r = db.get(NewsSource, sid)
    if not r:
        raise HTTPException(404, "Source not found")
    if not r.enabled:
        raise HTTPException(409, "Source is disabled")
    return _queue(db, admin, [r.key])


@router.post("/ingestion/run", status_code=202)
def run_all(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _queue(db, admin, None)


@router.get("/ingestion/logs")
def logs(source: str | None = None, pg: Page = Depends(), db: Session = Depends(get_db)):
    stmt = select(IngestionLog)
    if source:
        stmt = stmt.where(IngestionLog.source_key == source)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(IngestionLog.id.desc()).offset(pg.offset).limit(pg.size)).all()
    return {"data": [{c: getattr(r, c) for c in ("id", "job_id", "source_key", "status", "started_at", "finished_at",
                                                 "fetched", "saved", "duplicated", "rejected", "error")} for r in rows],
            "meta": {"page": pg.page, "page_size": pg.size, "total": total}}


@router.get("/ingestion/status")
def status(db: Session = Depends(get_db)):
    s = get_settings()
    last = db.scalar(select(IngestionJob).order_by(IngestionJob.id.desc()))
    running = db.scalar(select(IngestionJob).where(IngestionJob.status == "running"))
    return {"data": {
        "last_job": {"id": last.id, "status": last.status, "started_at": last.started_at, "finished_at": last.finished_at} if last else None,
        "running": bool(running), "timezone": s.timezone, "schedule_hours": s.ingest_hours,
        "next_runs": next_runs(utcnow(), s.ingest_hours, s.timezone)}}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    s = get_settings()
    cnt = dict(db.execute(select(Article.status, func.count()).group_by(Article.status)).all())
    dup = db.scalar(select(func.count()).select_from(ArticleSource).where(ArticleSource.is_primary.is_(False))) or 0
    srcs = db.scalars(select(NewsSource)).all()
    last_ok = db.scalar(select(func.max(IngestionJob.finished_at)).where(IngestionJob.status.in_(("success", "partial"))))
    return {"data": {
        "total_collected": sum(cnt.values()), "published": cnt.get("published", 0), "pending_review": cnt.get("pending", 0),
        "rejected": cnt.get("rejected", 0), "archived": cnt.get("archived", 0), "duplicate_discoveries_merged": dup,
        "connectors_total": len(srcs), "connectors_enabled": sum(r.enabled for r in srcs),
        "connectors_failed": sum(r.status == "error" for r in srcs),
        "connectors_unavailable": sum(r.enabled and r.status == "unavailable" for r in srcs),
        "last_successful_ingestion": last_ok,
        "next_scheduled_ingestion": next_runs(utcnow(), s.ingest_hours, s.timezone, 1)[0]}}
