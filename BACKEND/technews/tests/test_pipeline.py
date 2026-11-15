from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.connectors.base import Connector, RawItem
from app.models import (Article, ArticleLike, ArticleSource, ArticleView, IngestionJob, IngestionLog, NewsSource, User)
from app.schedule import next_runs
from app.services.categorize import categorize
from app.services.dedupe import normalize_title, similar
from app.services.ingest import process_item, run_ingestion
from app.services.ranking import recompute_rankings
from app.util import canonicalize_url, utcnow
from tests.conftest import make_article


class FakeConn(Connector):
    def __init__(self, key, items=None, boom=False, authority=50, kind="api", content_type="VERIFIED_NEWS", prior=0.3):
        self.key = self.name = key
        self.kind, self.authority, self.topic_prior = kind, authority, prior
        self._items, self._boom, self.ct = items or [], boom, content_type

    def fetch(self, client, s):
        if self._boom:
            raise RuntimeError("upstream down")
        return self._items


def raw(key, i, title, url, **kw):
    return RawItem(key, str(i), title, url, published_at=utcnow(), **kw)


# ---- categorisation -----------------------------------------------------------------------------------------------
def test_categorize_and_relevance():
    c = categorize("OpenAI releases new GPT-5 LLM with better reasoning", None, 0.1, None)
    assert c.category == "generative-ai" and c.relevance >= 0.5
    off = categorize("Local team wins the cricket final in India", None, 0.1, None)
    assert off.relevance < 0.2          # 'India' alone must not make it tech
    assert "clickbait_phrasing" in categorize("You won't believe this Python trick", None, 0.1, None).flags


# ---- duplicate detection ----------------------------------------------------------------------------------------
def test_url_canonicalisation():
    assert canonicalize_url("http://www.Example.com/a/?utm_source=x&b=1#frag") == "https://example.com/a?b=1"


def test_similarity_is_conservative():
    a = normalize_title("Apple releases iPhone 16 with new camera system")
    assert similar(a, normalize_title("Apple releases iPhone 16 with new camera system!"), .88, .7)
    assert not similar(a, normalize_title("Apple releases iPhone 17 with new camera system"), .88, .7)   # number differs
    assert not similar(normalize_title("Rust compiler gets faster builds"), normalize_title("Python gets faster interpreter builds"), .88, .7)


def test_same_story_from_three_sources_is_one_article(db, settings):
    tc = FakeConn("techcrunch", authority=90)
    gn = FakeConn("google_news", authority=80)
    hn = FakeConn("hackernews", authority=40, kind="api")
    title = "Anthropic raises new funding for Claude AI agents"
    for conn, i, url in [(hn, 1, "https://techcrunch.com/2026/story?utm_source=hn"), (gn, 2, "https://news.google.com/rss/articles/OPAQUE"),
                         (tc, 3, "https://techcrunch.com/2026/story")]:
        r = process_item(db, raw(conn.key, i, title, url, publisher="TechCrunch" if conn is not hn else "techcrunch.com"), conn, settings)
    assert db.scalar(select(func.count()).select_from(Article)) == 1
    a = db.scalar(select(Article))
    assert len(a.sources) == 3 and a.source_key == "techcrunch" and a.original_url == "https://techcrunch.com/2026/story"
    assert sum(s.is_primary for s in a.sources) == 1


def test_resighting_same_external_id_not_duplicated(db, settings):
    c = FakeConn("hackernews")
    it = raw("hackernews", 1, "New open source LLM framework released", "https://e.com/x")
    assert process_item(db, it, c, settings) == "saved"
    assert process_item(db, it, c, settings) == "duplicated"


def test_validation_and_unsafe_urls(db, settings):
    c = FakeConn("hackernews")
    assert process_item(db, raw("hackernews", 1, "Valid title about Python", "javascript:alert(1)"), c, settings) == "invalid"
    assert process_item(db, raw("hackernews", 2, "short", "https://e.com"), c, settings) == "invalid"


def test_social_and_flagged_content_needs_review_and_low_relevance_rejected(db, settings):
    s = FakeConn("reddit", kind="social")
    process_item(db, raw("reddit", 1, "New open source Python framework for LLM agents", "https://reddit.com/r/x/1"), s, settings)
    assert db.scalar(select(Article)).status == "pending"
    api = FakeConn("hackernews", prior=0.1)
    assert process_item(db, raw("hackernews", 2, "Gardening tips for the autumn season", "https://e.com/g"), api, settings) in ("rejected",)


def test_thumbnails_not_hotlinked_by_default(db, settings):
    process_item(db, raw("hackernews", 1, "New Rust compiler release is out", "https://e.com/r", thumbnail="https://img.e.com/a.png"), FakeConn("hackernews"), settings)
    assert db.scalar(select(Article)).thumbnail_url is None


# ---- ingestion run: isolation + logs --------------------------------------------------------------------------
def test_failing_connector_does_not_stop_others(factory, settings):
    with factory() as db:
        for k in ("bad", "good"):
            db.add(NewsSource(key=k, name=k, kind="api", access="free", enabled=True))
        db.commit()
    good = FakeConn("good", [raw("good", 1, "New Python framework for LLM agents ships", "https://e.com/1")])
    jid = run_ingestion(factory, settings, connectors=[FakeConn("bad", boom=True), good], client=object())
    with factory() as db:
        job = db.get(IngestionJob, jid)
        logs = {l.source_key: l for l in job.logs}
        assert job.status == "partial"
        assert logs["bad"].status == "failed" and "upstream down" in logs["bad"].error
        assert logs["good"].status == "success" and logs["good"].saved == 1 and logs["good"].fetched == 1
        bad = db.scalar(select(NewsSource).where(NewsSource.key == "bad"))
        assert bad.status == "error" and bad.last_failure_at and not bad.last_success_at
        assert db.scalar(select(NewsSource).where(NewsSource.key == "good")).last_success_at
        assert db.scalar(select(func.count()).select_from(Article)) == 1


def test_unavailable_connector_is_skipped_with_reason(factory, settings):
    class NeedsKey(FakeConn):
        def availability(self, s):
            return False, "no credentials"
    with factory() as db:
        db.add(NewsSource(key="paid", name="paid", kind="api", access="paid", enabled=True))
        db.commit()
    jid = run_ingestion(factory, settings, connectors=[NeedsKey("paid")], client=object())
    with factory() as db:
        l = db.scalar(select(IngestionLog))
        assert l.status == "skipped" and l.error == "no credentials"
        assert db.scalar(select(NewsSource).where(NewsSource.key == "paid")).status == "unavailable"


# ---- ranking ------------------------------------------------------------------------------------------------------------
def test_ranking_uses_unique_engagement_and_decay(db, settings):
    hot = make_article(db, published_at=utcnow() - timedelta(hours=2))
    old = make_article(db, published_at=utcnow() - timedelta(days=6))
    quiet = make_article(db, published_at=utcnow() - timedelta(hours=2))
    for uid in (1, 2, 9):
        db.add(ArticleLike(user_id=uid, article_id=hot.id))
        db.add(ArticleLike(user_id=uid, article_id=old.id))
    for i in range(5):
        db.add(ArticleView(article_id=hot.id, viewer_key=f"v{i}", day=utcnow().date()))
        db.add(ArticleView(article_id=old.id, viewer_key=f"v{i}", day=utcnow().date()))
    db.commit()
    recompute_rankings(db, settings)
    for a in (hot, old, quiet):
        db.refresh(a)
    assert hot.trending_score > old.trending_score > quiet.trending_score >= 0     # same engagement, older decays
    r = {x.article_id: x for x in db.scalars(select(__import__("app.models", fromlist=["ArticleRanking"]).ArticleRanking))}
    assert r[hot.id].views_7d == 5 and r[hot.id].likes_7d == 3


def test_duplicate_like_and_view_rejected_by_db(db):
    from sqlalchemy.exc import IntegrityError
    a = make_article(db)
    db.add(ArticleLike(user_id=1, article_id=a.id)); db.commit()
    db.add(ArticleLike(user_id=1, article_id=a.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(ArticleView(article_id=a.id, viewer_key="k", day=utcnow().date())); db.commit()
    db.add(ArticleView(article_id=a.id, viewer_key="k", day=utcnow().date()))
    with pytest.raises(IntegrityError):
        db.commit()


def test_weights_are_configurable(db, settings):
    a = make_article(db, published_at=utcnow() - timedelta(hours=1))
    db.add(ArticleView(article_id=a.id, viewer_key="v", day=utcnow().date())); db.commit()
    recompute_rankings(db, settings)
    base = db.refresh(a) or a.trending_score
    recompute_rankings(db, settings.model_copy(update={"w_views": 0.0}))
    db.refresh(a)
    assert a.trending_score < base


# ---- scheduler -------------------------------------------------------------------------------------------------------
def test_celery_beat_runs_every_8_hours_ist():
    from app.celery_app import celery
    entry = celery.conf.beat_schedule["ingest-every-8h"]
    assert entry["schedule"].hour == {0, 8, 16} and entry["schedule"].minute == {0}
    assert celery.conf.timezone == "Asia/Kolkata"
    assert len([k for k in celery.conf.beat_schedule if "ingest" in k]) == 1   # static: restart can't duplicate it


def test_next_runs_in_ist():
    from datetime import datetime, timezone
    nxt = next_runs(datetime(2026, 11, 15, 2, 0, tzinfo=timezone.utc), "0,8,16", "Asia/Kolkata", 3)   # 07:30 IST
    assert [t.hour for t in nxt] == [8, 16, 0] and nxt[0].day == 15 and nxt[2].day == 16
