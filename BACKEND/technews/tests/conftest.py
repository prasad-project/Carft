import os

os.environ.update(DATABASE_URL="sqlite://", RATE_LIMIT_STORAGE="memory://", RATE_LIMIT_DEFAULT="10000/minute",
                  JWT_SECRET="test-secret", VIEWER_HASH_SECRET="x")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import get_db
from app.main import app
from app.models import Article, Base, User
from app.security import create_access_token
from app.services.ingest import seed_reference_data
from app.util import utcnow


@pytest.fixture()
def factory():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    f = sessionmaker(bind=eng, expire_on_commit=False)
    with f() as db:
        seed_reference_data(db)
        db.add_all([User(id=1, email="a@x.io", display_name="Ann"), User(id=2, email="b@x.io"),
                    User(id=9, email="root@x.io", role="admin")])
        db.commit()
    return f


@pytest.fixture()
def db(factory):
    with factory() as s:
        yield s


@pytest.fixture()
def client(factory, monkeypatch):
    def _db():
        with factory() as s:
            yield s
    app.dependency_overrides[get_db] = _db
    queued = []
    monkeypatch.setattr("app.api.admin.enqueue_ingestion", lambda jid, keys=None: queued.append((jid, keys)))
    c = TestClient(app)
    c.queued = queued
    yield c
    app.dependency_overrides.clear()


def auth(uid, role="user"):
    return {"Authorization": f"Bearer {create_access_token(uid, role)}"}


@pytest.fixture()
def settings():
    return Settings(http_backoff=0, enable_terms_restricted_sources=True)


_n = 0


def make_article(db, **kw):
    global _n
    _n += 1
    d = dict(title=f"Story number {_n}", slug=f"story-{_n}", title_norm=f"story number {_n}", source_key="hackernews",
             source_name="Hacker News", source_type="api", original_url=f"https://e.com/{_n}",
             canonical_url=f"https://e.com/{_n}", content_type="VERIFIED_NEWS", status="published",
             category="programming", relevance_score=0.8, published_at=utcnow())
    d.update(kw)
    a = Article(**d)
    db.add(a)
    db.commit()
    return a
