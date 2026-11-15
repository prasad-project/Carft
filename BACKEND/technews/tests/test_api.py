from datetime import timedelta

from app.models import ArticleRanking
from app.util import utcnow
from tests.conftest import auth, make_article


def test_empty_states(client):
    for p in ("", "/top", "/trending", "/latest", "/most-read", "/most-liked", "/most-discussed", "/collections/ai-ml"):
        r = client.get("/api/news" + p)
        assert r.status_code == 200 and r.json() == {"data": [], "meta": {"page": 1, "page_size": 20, "total": 0}}


def test_public_reads_only_published_and_paginates(client, db):
    for i in range(5):
        make_article(db, published_at=utcnow() - timedelta(hours=i))
    make_article(db, status="pending"); make_article(db, status="rejected")
    r = client.get("/api/news?page_size=2&page=3").json()
    assert r["meta"]["total"] == 5 and len(r["data"]) == 1
    assert client.get("/api/news?page_size=500").status_code == 422
    ids = [a["id"] for a in client.get("/api/news/latest").json()["data"]]
    assert ids == sorted(ids)            # newest first == insertion order here


def test_search_filter_and_slug(client, db):
    a = make_article(db, title="Rust 2.0 is here", category="programming")
    make_article(db, title="Cloud outage", category="cloud-computing")
    assert [x["id"] for x in client.get("/api/news?q=rust").json()["data"]] == [a.id]
    assert client.get("/api/news?category=cloud-computing").json()["meta"]["total"] == 1
    assert client.get("/api/news?q=%25").json()["meta"]["total"] == 0           # wildcard escaped
    assert client.get(f"/api/news/{a.slug}").json()["data"]["title"] == "Rust 2.0 is here"
    assert client.get("/api/news/nope").status_code == 404


def test_like_save_require_auth_and_are_idempotent(client, db):
    a = make_article(db)
    assert client.post(f"/api/news/{a.id}/like").status_code == 401
    h = auth(1)
    assert client.post(f"/api/news/{a.id}/like", headers=h).json()["likes_count"] == 1
    assert client.post(f"/api/news/{a.id}/like", headers=h).json()["likes_count"] == 1     # no double count
    assert client.post(f"/api/news/{a.id}/like", headers=auth(2)).json()["likes_count"] == 2
    assert client.delete(f"/api/news/{a.id}/like", headers=h).json()["likes_count"] == 1
    client.post(f"/api/news/{a.id}/save", headers=h); client.post(f"/api/news/{a.id}/save", headers=h)
    assert [x["id"] for x in client.get("/api/news/saved", headers=h).json()["data"]] == [a.id]
    assert client.get("/api/news/saved", headers=auth(2)).json()["meta"]["total"] == 0
    client.delete(f"/api/news/{a.id}/save", headers=h)
    assert client.get("/api/news/saved", headers=h).json()["meta"]["total"] == 0
    client.post(f"/api/news/{a.id}/like", headers=h)
    assert client.get("/api/news/liked", headers=h).json()["meta"]["total"] == 1
    assert client.get(f"/api/news/{a.slug}", headers=h).json()["data"]["liked_by_me"] is True


def test_cannot_interact_with_unpublished(client, db):
    a = make_article(db, status="pending")
    assert client.post(f"/api/news/{a.id}/like", headers=auth(1)).status_code == 404


def test_comments_crud_and_permissions(client, db):
    a = make_article(db)
    h1, h2 = auth(1), auth(2)
    assert client.post(f"/api/news/{a.id}/comments", json={"body": "x"}).status_code == 401
    c = client.post(f"/api/news/{a.id}/comments", json={"body": "<script>alert(1)</script>Nice read"}, headers=h1).json()["data"]
    assert c["body"] == "alert(1)Nice read" and c["author"] == "Ann"
    assert client.post(f"/api/news/{a.id}/comments", json={"body": ""}, headers=h1).status_code == 422
    assert client.post(f"/api/news/{a.id}/comments", json={"body": "<b></b>"}, headers=h1).status_code == 422
    assert client.patch(f"/api/news/{a.id}/comments/{c['id']}", json={"body": "hack"}, headers=h2).status_code == 403
    assert client.patch(f"/api/news/{a.id}/comments/{c['id']}", json={"body": "edited"}, headers=h1).json()["data"]["body"] == "edited"
    assert client.get(f"/api/news/{a.slug}").json()["data"]["comments_count"] == 1
    assert client.delete(f"/api/news/{a.id}/comments/{c['id']}", headers=h2).status_code == 403
    assert client.delete(f"/api/news/{a.id}/comments/{c['id']}", headers=h1).status_code == 204
    assert client.get(f"/api/news/{a.id}/comments").json()["meta"]["total"] == 0
    assert client.get(f"/api/news/{a.slug}").json()["data"]["comments_count"] == 0


def test_qualified_views_are_unique_per_viewer_per_day(client, db):
    a = make_article(db)
    assert client.post(f"/api/news/{a.id}/view", json={"dwell_seconds": 1}).json()["counted"] is False   # too short
    assert client.post(f"/api/news/{a.id}/view", json={"dwell_seconds": 30}).json()["counted"] is True
    assert client.post(f"/api/news/{a.id}/view", json={"dwell_seconds": 30}).json()["counted"] is False  # same viewer/day
    assert client.post(f"/api/news/{a.id}/view", json={"dwell_seconds": 30}, headers=auth(1)).json()["counted"] is True
    assert client.get(f"/api/news/{a.slug}").json()["data"]["views_count"] == 2


def test_most_collections_use_rankings(client, db):
    a, b = make_article(db), make_article(db)
    db.add_all([ArticleRanking(article_id=a.id, likes_7d=3, views_7d=1, comments_7d=0),
                ArticleRanking(article_id=b.id, likes_7d=0, views_7d=9, comments_7d=2)]); db.commit()
    assert [x["id"] for x in client.get("/api/news/most-liked").json()["data"]] == [a.id]
    assert [x["id"] for x in client.get("/api/news/most-read").json()["data"]] == [b.id, a.id]
    assert [x["id"] for x in client.get("/api/news/most-discussed").json()["data"]] == [b.id]


def test_collections_are_separate(client, db):
    ai = make_article(db, category="machine-learning")
    dev = make_article(db, content_type="DEVELOPER_DISCOVERY", category="open-source")
    res = make_article(db, content_type="RESEARCH_UPDATE", category="research")
    ids = lambda n: {x["id"] for x in client.get(f"/api/news/collections/{n}").json()["data"]}
    assert ids("ai-ml") == {ai.id} and ids("developer-discoveries") == {dev.id} and ids("research-open-source") == {dev.id, res.id}
    assert client.get("/api/news/collections/zzz").status_code == 404


# ---- admin -----------------------------------------------------------------------------------------------------------------
def test_admin_endpoints_forbidden_for_users_and_anonymous(client, db):
    a = make_article(db)
    for method, path in [("get", "/api/admin/news"), ("get", "/api/admin/dashboard"), ("get", "/api/admin/sources"),
                         ("post", "/api/admin/ingestion/run"), ("post", f"/api/admin/news/{a.id}/publish"),
                         ("delete", f"/api/admin/news/{a.id}"), ("get", "/api/admin/ingestion/logs"), ("post", "/api/admin/news")]:
        assert getattr(client, method)(path).status_code == 401
        assert getattr(client, method)(path, headers=auth(1)).status_code == 403
    assert client.post("/api/admin/ingestion/run", headers=auth(1, role="admin")).status_code == 403   # token claim is ignored; DB role rules


def test_admin_editorial_workflow_and_audit(client, db):
    from sqlalchemy import select
    from app.models import AuditLog
    a = make_article(db, status="pending")
    h = auth(9)
    assert client.get("/api/news").json()["meta"]["total"] == 0
    assert client.post(f"/api/admin/news/{a.id}/publish", headers=h).status_code == 200
    assert client.get("/api/news").json()["meta"]["total"] == 1
    r = client.patch(f"/api/admin/news/{a.id}", json={"title": "Edited headline here", "category": "cybersecurity", "tags": ["Zero Day"], "is_featured": True}, headers=h).json()["data"]
    assert r["category"] == "cybersecurity" and r["tags"] == ["Zero Day"] and r["is_featured"]
    assert client.patch(f"/api/admin/news/{a.id}", json={"category": "bogus"}, headers=h).status_code == 422
    client.post(f"/api/admin/news/{a.id}/reject", json={"reason": "spam"}, headers=h)
    assert client.get("/api/news").json()["meta"]["total"] == 0
    assert client.get("/api/admin/news?status=rejected", headers=h).json()["meta"]["total"] == 1
    assert client.delete(f"/api/admin/news/{a.id}", headers=h).status_code == 204
    actions = [x.action for x in db.scalars(select(AuditLog))]
    assert actions == ["published_article", "edit_article", "rejected_article", "delete_article"]


def test_admin_manual_video_validates_url(client):
    h = auth(9)
    assert client.post("/api/admin/news", json={"title": "My conference talk", "url": "javascript:alert(1)"}, headers=h).status_code == 422
    r = client.post("/api/admin/news", json={"title": "My conference talk", "url": "https://example.com/v", "publish": True}, headers=h)
    assert r.status_code == 201 and r.json()["data"]["content_type"] == "MANUAL_VIDEO"


def test_sources_dashboard_and_manual_fetch(client, db):
    h = auth(9)
    srcs = client.get("/api/admin/sources", headers=h).json()["data"]
    by = {s["key"]: s for s in srcs}
    assert len(srcs) == 11 and by["hackernews"]["enabled"] and not by["techcrunch"]["enabled"] and not by["x"]["enabled"]
    assert by["x"]["access"] == "paid" and by["x"]["available_now"] is False and by["x"]["status_reason"]
    assert client.post(f"/api/admin/sources/{by['x']['id']}/fetch", headers=h).status_code == 409     # disabled
    r = client.post(f"/api/admin/sources/{by['hackernews']['id']}/fetch", headers=h)
    assert r.status_code == 202 and client.queued == [(r.json()["data"]["job_id"], ["hackernews"])]
    assert client.patch(f"/api/admin/sources/{by['techcrunch']['id']}", json={"enabled": True}, headers=h).json()["data"]["enabled"]
    assert client.patch(f"/api/admin/sources/{by['techcrunch']['id']}", json={"quality_weight": 3}, headers=h).status_code == 422
    d = client.get("/api/admin/dashboard", headers=h).json()["data"]
    assert d["connectors_total"] == 11 and d["connectors_enabled"] == 7 and "next_scheduled_ingestion" in d
    st = client.get("/api/admin/ingestion/status", headers=h).json()["data"]
    assert len(st["next_runs"]) == 3 and st["schedule_hours"] == "0,8,16"
