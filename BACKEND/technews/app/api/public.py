import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import (Article, ArticleComment, ArticleLike, ArticleRanking, ArticleView, Category, SavedArticle, Tag,
                        User)
from app.security import current_user, current_user_optional, viewer_key
from app.util import utcnow

router = APIRouter(prefix="/api/news", tags=["news"])
R = ArticleRanking


class Page:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)):
        self.page, self.size = page, page_size

    @property
    def offset(self):
        return (self.page - 1) * self.size


def _c(col):
    return func.coalesce(col, 0)


def published():
    return select(Article).outerjoin(R, R.article_id == Article.id).where(Article.status == "published")


def serialize(a: Article, liked=frozenset(), saved=frozenset()) -> dict:
    return {
        "id": a.id, "title": a.title, "slug": a.slug, "source_name": a.source_name, "source_type": a.source_type,
        "original_url": a.original_url, "canonical_url": a.canonical_url, "author_name": a.author_name,
        "publisher_name": a.publisher_name, "thumbnail_url": a.thumbnail_url, "description": a.description,
        "summary": a.summary, "summary_is_ai": a.summary_is_ai, "category": a.category,
        "tags": [t.name for t in a.tags], "published_at": a.published_at, "fetched_at": a.fetched_at,
        "content_type": a.content_type, "relevance_score": a.relevance_score, "popularity_score": a.popularity_score,
        "trending_score": a.trending_score, "views_count": a.views_count, "likes_count": a.likes_count,
        "comments_count": a.comments_count, "status": a.status, "is_featured": a.is_featured,
        "is_trending": a.is_trending, "other_sources": [{"source": x.source_key, "url": x.url} for x in a.sources if not x.is_primary],
        "liked_by_me": a.id in liked, "saved_by_me": a.id in saved,
    }


def respond(db, user, stmt, pg: Page):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset(pg.offset).limit(pg.size)).all()
    liked = saved = set()
    if user and rows:
        ids = [a.id for a in rows]
        liked = set(db.scalars(select(ArticleLike.article_id).where(ArticleLike.user_id == user.id, ArticleLike.article_id.in_(ids))))
        saved = set(db.scalars(select(SavedArticle.article_id).where(SavedArticle.user_id == user.id, SavedArticle.article_id.in_(ids))))
    return {"data": [serialize(a, liked, saved) for a in rows],
            "meta": {"page": pg.page, "page_size": pg.size, "total": total}}


SORTS = {
    "latest": lambda: [Article.published_at.desc()],
    "trending": lambda: [_c(R.trending_score).desc(), Article.published_at.desc()],
    "top": lambda: [Article.is_featured.desc(), (_c(R.editorial_score) * 0.6 + _c(R.freshness_score) * 0.4).desc()],
    "views": lambda: [_c(R.views_7d).desc(), Article.published_at.desc()],
    "likes": lambda: [_c(R.likes_7d).desc(), Article.published_at.desc()],
    "comments": lambda: [_c(R.comments_7d).desc(), Article.published_at.desc()],
}
AI_CATS = ("artificial-intelligence", "machine-learning", "generative-ai", "data-science")
COLLECTIONS = {
    "ai-ml": lambda: Article.category.in_(AI_CATS),
    "developer-discoveries": lambda: or_(Article.content_type.in_(("DEVELOPER_DISCOVERY", "PRODUCT_RELEASE")),
                                         Article.category.in_(("open-source", "developer-tools"))),
    "research-open-source": lambda: or_(Article.content_type == "RESEARCH_UPDATE",
                                        Article.category.in_(("research", "open-source"))),
}


@router.get("")
def list_news(q: str | None = Query(None, max_length=100), category: str | None = None, content_type: str | None = None,
              tag: str | None = None, sort: str = Query("latest", pattern="^(latest|trending|top|views|likes|comments)$"),
              pg: Page = Depends(), db: Session = Depends(get_db), user: User | None = Depends(current_user_optional)):
    stmt = published()
    if q:
        esc = re.sub(r"([%_\\])", r"\\\1", q)
        stmt = stmt.where(Article.title.ilike(f"%{esc}%", escape="\\"))
    if category:
        stmt = stmt.where(Article.category == category)
    if content_type:
        stmt = stmt.where(Article.content_type == content_type)
    if tag:
        stmt = stmt.where(Article.tags.any(Tag.slug == tag))
    return respond(db, user, stmt.order_by(*SORTS[sort]()), pg)


@router.get("/top")
def top(pg: Page = Depends(), db: Session = Depends(get_db), user=Depends(current_user_optional)):
    stmt = published().where(Article.published_at >= utcnow() - timedelta(days=7))
    return respond(db, user, stmt.order_by(*SORTS["top"]()), pg)


@router.get("/trending")
def trending(pg: Page = Depends(), db: Session = Depends(get_db), user=Depends(current_user_optional)):
    return respond(db, user, published().order_by(*SORTS["trending"]()), pg)


@router.get("/latest")
def latest(pg: Page = Depends(), db: Session = Depends(get_db), user=Depends(current_user_optional)):
    return respond(db, user, published().order_by(*SORTS["latest"]()), pg)


@router.get("/most-read")
def most_read(pg: Page = Depends(), db: Session = Depends(get_db), user=Depends(current_user_optional)):
    return respond(db, user, published().where(R.views_7d > 0).order_by(*SORTS["views"]()), pg)


@router.get("/most-liked")
def most_liked(pg: Page = Depends(), db: Session = Depends(get_db), user=Depends(current_user_optional)):
    return respond(db, user, published().where(R.likes_7d > 0).order_by(*SORTS["likes"]()), pg)


@router.get("/most-discussed")
def most_discussed(pg: Page = Depends(), db: Session = Depends(get_db), user=Depends(current_user_optional)):
    return respond(db, user, published().where(R.comments_7d > 0).order_by(*SORTS["comments"]()), pg)


@router.get("/collections/{name}")
def collection(name: str, pg: Page = Depends(), db: Session = Depends(get_db), user=Depends(current_user_optional)):
    if name not in COLLECTIONS:
        raise HTTPException(404, "Unknown collection")
    return respond(db, user, published().where(COLLECTIONS[name]()).order_by(*SORTS["latest"]()), pg)


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Article.category, func.count()).where(Article.status == "published").group_by(Article.category)).all())
    return {"data": [{"slug": c.slug, "name": c.name, "count": counts.get(c.slug, 0)} for c in db.scalars(select(Category).order_by(Category.name))]}


@router.get("/saved")
def saved(pg: Page = Depends(), db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = published().join(SavedArticle, SavedArticle.article_id == Article.id).where(SavedArticle.user_id == user.id).order_by(SavedArticle.created_at.desc())
    return respond(db, user, stmt, pg)


@router.get("/liked")
def liked(pg: Page = Depends(), db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = published().join(ArticleLike, ArticleLike.article_id == Article.id).where(ArticleLike.user_id == user.id).order_by(ArticleLike.created_at.desc())
    return respond(db, user, stmt, pg)


def _article(db, article_id: int) -> Article:
    a = db.get(Article, article_id)
    if not a or a.status != "published":
        raise HTTPException(404, "Article not found")
    return a


@router.get("/{slug}")
def detail(slug: str, db: Session = Depends(get_db), user=Depends(current_user_optional)):
    a = db.scalar(select(Article).where(Article.slug == slug, Article.status == "published"))
    if not a:
        raise HTTPException(404, "Article not found")
    liked = {a.id} if user and db.scalar(select(ArticleLike.id).where(ArticleLike.user_id == user.id, ArticleLike.article_id == a.id)) else set()
    saved = {a.id} if user and db.scalar(select(SavedArticle.id).where(SavedArticle.user_id == user.id, SavedArticle.article_id == a.id)) else set()
    return {"data": serialize(a, liked, saved)}


class ViewIn(BaseModel):
    dwell_seconds: int = Field(ge=0, le=86400)


@router.post("/{article_id}/view", status_code=202)
def track_view(article_id: int, body: ViewIn, request: Request, db: Session = Depends(get_db), user=Depends(current_user_optional)):
    a = _article(db, article_id)
    if body.dwell_seconds < get_settings().min_view_dwell_seconds:
        return {"counted": False}
    db.add(ArticleView(article_id=a.id, viewer_key=viewer_key(request, user), user_id=user.id if user else None, day=utcnow().date()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"counted": False}
    a.views_count = db.scalar(select(func.count()).select_from(ArticleView).where(ArticleView.article_id == a.id))
    db.commit()
    return {"counted": True}


def _toggle(db, model, article_id, user, add: bool, counter: str | None):
    a = _article(db, article_id)
    if add:
        db.add(model(user_id=user.id, article_id=a.id))
        try:
            db.commit()
        except IntegrityError:           # unique constraint => already liked/saved; idempotent
            db.rollback()
    else:
        row = db.scalar(select(model).where(model.user_id == user.id, model.article_id == a.id))
        if row:
            db.delete(row)
            db.commit()
    if counter:
        setattr(a, counter, db.scalar(select(func.count()).select_from(model).where(model.article_id == a.id)))
        db.commit()
    return {"ok": True, "likes_count": a.likes_count}


@router.post("/{article_id}/like")
def like(article_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    return _toggle(db, ArticleLike, article_id, user, True, "likes_count")


@router.delete("/{article_id}/like")
def unlike(article_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    return _toggle(db, ArticleLike, article_id, user, False, "likes_count")


@router.post("/{article_id}/save")
def save(article_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    return _toggle(db, SavedArticle, article_id, user, True, None)


@router.delete("/{article_id}/save")
def unsave(article_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    return _toggle(db, SavedArticle, article_id, user, False, None)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _clean(body: str) -> str:
    body = re.sub(r"<[^>]*>", "", body)
    body = re.sub(r"[\x00-\x08\x0b-\x1f]", "", body).strip()
    if not body:
        raise HTTPException(422, "Comment is empty after sanitising")
    return body


def _comment(c: ArticleComment, users: dict) -> dict:
    u = users.get(c.user_id)
    return {"id": c.id, "article_id": c.article_id, "user_id": c.user_id,
            "author": (u.display_name if u and u.display_name else f"user-{c.user_id}"),
            "body": c.body, "created_at": c.created_at, "updated_at": c.updated_at}


def _recount(db, a):
    a.comments_count = db.scalar(select(func.count()).select_from(ArticleComment).where(
        ArticleComment.article_id == a.id, ArticleComment.is_deleted.is_(False)))
    db.commit()


@router.get("/{article_id}/comments")
def list_comments(article_id: int, pg: Page = Depends(), db: Session = Depends(get_db)):
    _article(db, article_id)
    stmt = select(ArticleComment).where(ArticleComment.article_id == article_id, ArticleComment.is_deleted.is_(False))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(ArticleComment.created_at.desc()).offset(pg.offset).limit(pg.size)).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({c.user_id for c in rows})))} if rows else {}
    return {"data": [_comment(c, users) for c in rows], "meta": {"page": pg.page, "page_size": pg.size, "total": total}}


@router.post("/{article_id}/comments", status_code=201)
def add_comment(article_id: int, body: CommentIn, db: Session = Depends(get_db), user=Depends(current_user)):
    a = _article(db, article_id)
    c = ArticleComment(article_id=a.id, user_id=user.id, body=_clean(body.body))
    db.add(c)
    db.commit()
    _recount(db, a)
    return {"data": _comment(c, {user.id: user})}


@router.patch("/{article_id}/comments/{comment_id}")
def edit_comment(article_id: int, comment_id: int, body: CommentIn, db: Session = Depends(get_db), user=Depends(current_user)):
    c = db.get(ArticleComment, comment_id)
    if not c or c.article_id != article_id or c.is_deleted:
        raise HTTPException(404, "Comment not found")
    if c.user_id != user.id:
        raise HTTPException(403, "You can only edit your own comments")
    c.body = _clean(body.body)
    db.commit()
    return {"data": _comment(c, {user.id: user})}


@router.delete("/{article_id}/comments/{comment_id}", status_code=204)
def delete_comment(article_id: int, comment_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    c = db.get(ArticleComment, comment_id)
    if not c or c.article_id != article_id or c.is_deleted:
        raise HTTPException(404, "Comment not found")
    if c.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "You can only delete your own comments")
    c.is_deleted = True
    db.commit()
    _recount(db, db.get(Article, article_id))
