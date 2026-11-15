import math
from datetime import timedelta

from sqlalchemy import func, select

from app.models import Article, ArticleComment, ArticleLike, ArticleRanking, ArticleSource, ArticleView, NewsSource
from app.util import aware, utcnow


def lognorm(x: float, mx: float) -> float:
    return math.log1p(x) / math.log1p(mx) if mx > 0 else 0.0


def decay(age_hours: float, half_life: float) -> float:
    return 0.5 ** (max(age_hours, 0) / half_life)


def _counts(db, model, col_filter, cutoff):
    q = select(model.article_id, func.count()).where(model.created_at >= cutoff)
    if col_filter is not None:
        q = q.where(col_filter)
    return dict(db.execute(q.group_by(model.article_id)).all())


def recompute_rankings(db, s, now=None) -> int:
    """Rolling-window ranking. Likes are unique per user (DB constraint), views unique per viewer/day,
    so one account cannot inflate a story by repeating actions."""
    now = now or utcnow()
    cutoff = now - timedelta(days=s.rank_window_days)
    arts = db.scalars(select(Article).where(Article.status == "published",
                                            Article.published_at >= now - timedelta(days=30))).all()
    if not arts:
        return 0
    views = _counts(db, ArticleView, None, cutoff)
    likes = _counts(db, ArticleLike, None, cutoff)
    comments = _counts(db, ArticleComment, ArticleComment.is_deleted.is_(False), cutoff)
    ext: dict[int, float] = {}
    for aid, m in db.execute(select(ArticleSource.article_id, ArticleSource.metrics)):
        ext[aid] = max(ext.get(aid, 0.0), float((m or {}).get("engagement", 0)))
    quality = {k: q for k, q in db.execute(select(NewsSource.key, NewsSource.quality_weight))}
    mv, ml, mc = max(views.values(), default=0), max(likes.values(), default=0), max(comments.values(), default=0)
    me = max(ext.values(), default=0)
    existing = {r.article_id: r for r in db.scalars(select(ArticleRanking))}

    for a in arts:
        age_h = (now - aware(a.published_at)).total_seconds() / 3600
        v, l, c = views.get(a.id, 0), likes.get(a.id, 0), comments.get(a.id, 0)
        nv, nl, nc, ne = lognorm(v, mv), lognorm(l, ml), lognorm(c, mc), lognorm(ext.get(a.id, 0), me)
        fresh = decay(age_h, s.freshness_half_life_hours)
        editorial = a.relevance_score * quality.get(a.source_key, 0.5)
        wsum = (s.w_views + s.w_likes + s.w_comments) or 1
        community = (s.w_views * nv + s.w_likes * nl + s.w_comments * nc) / wsum
        raw = (s.w_views * nv + s.w_likes * nl + s.w_comments * nc
               + s.w_fresh_rel * fresh * a.relevance_score + s.w_external * ne)
        trending = raw * decay(age_h, s.trending_half_life_hours)
        r = existing.get(a.id) or ArticleRanking(article_id=a.id)
        r.views_7d, r.likes_7d, r.comments_7d = v, l, c
        r.editorial_score, r.community_score = round(editorial, 5), round(community, 5)
        r.freshness_score, r.trending_score, r.computed_at = round(fresh, 5), round(trending, 5), now
        db.add(r)
        a.trending_score, a.popularity_score = r.trending_score, r.community_score
    db.commit()
    return len(arts)
