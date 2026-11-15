import httpx
import pytest

from app.connectors import BY_KEY
from app.connectors.feeds import resolve_google_news_url
from app.http import ConnectorError, RateLimited, fetch


def client_for(routes):
    def handler(req: httpx.Request):
        for key, resp in routes.items():
            if key in str(req.url):
                return resp(req) if callable(resp) else httpx.Response(200, json=resp) if not isinstance(resp, (str, bytes)) else httpx.Response(200, content=resp)
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Startup raises $20M for AI agents - TechCrunch</title><link>https://techcrunch.com/a</link><guid>g1</guid>
<pubDate>Mon, 02 Mar 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description>
<source url="https://techcrunch.com">TechCrunch</source></item></channel></rss>"""


def test_hackernews(settings):
    c = client_for({
        "topstories": [1, 2], "beststories": [], "newstories": [], "showstories": [], "askstories": [],
        "item/1.json": {"id": 1, "type": "story", "title": "Rust 2.0 released", "url": "https://www.rust-lang.org/x", "by": "u", "time": 1700000000, "score": 100, "descendants": 20},
        "item/2.json": {"id": 2, "type": "job", "title": "Hiring"}})
    items = BY_KEY["hackernews"].fetch(c, settings)
    assert len(items) == 1 and items[0].publisher == "rust-lang.org" and items[0].engagement == 120


def test_devto(settings):
    c = client_for({"dev.to/api/articles": [{"id": 5, "title": "Learn FastAPI", "url": "https://dev.to/x", "tag_list": "python, api",
                                              "positive_reactions_count": 3, "comments_count": 1, "user": {"name": "Z"}, "published_at": "2026-01-01T00:00:00Z"}]})
    it = BY_KEY["devto"].fetch(c, settings)[0]
    assert it.tags == ["python", "api"] and it.engagement == 4 and it.content_type == "DEVELOPER_DISCOVERY"


def test_arxiv(settings):
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1</id><title>A  Study
 of Agents</title><summary>abs</summary><published>2026-01-02T00:00:00Z</published><link href="http://arxiv.org/abs/1"/>
<author><name>X</name></author></entry></feed>"""
    it = BY_KEY["arxiv"].fetch(client_for({"arxiv.org/api": atom}), settings)[0]
    assert it.title == "A Study of Agents" and it.content_type == "RESEARCH_UPDATE"


def test_huggingface(settings):
    c = client_for({"huggingface.co/api/models": [{"id": "org/m", "likes": 7, "pipeline_tag": "text-generation", "createdAt": "2026-01-01T00:00:00Z"}],
                    "huggingface.co/api/datasets": []})
    it = BY_KEY["huggingface"].fetch(c, settings)[0]
    assert it.url == "https://huggingface.co/org/m" and it.engagement == 7


def test_github(settings):
    s = settings.model_copy(update={"github_watch_repos": "a/b"})
    c = client_for({"search/repositories": {"items": [{"id": 1, "full_name": "o/r", "description": "d", "html_url": "https://github.com/o/r",
                                                       "owner": {"login": "o"}, "stargazers_count": 99, "created_at": "2026-01-01T00:00:00Z", "topics": ["ai"], "language": "Python"}]},
                    "repos/a/b/releases": [{"id": 3, "tag_name": "v1", "html_url": "https://github.com/a/b/r/v1", "draft": False, "prerelease": False, "published_at": "2026-01-01T00:00:00Z"},
                                           {"id": 4, "tag_name": "v2-rc", "html_url": "https://github.com/a/b/r/v2", "draft": False, "prerelease": True}]})
    items = BY_KEY["github"].fetch(c, s)
    assert {i.content_type for i in items} == {"DEVELOPER_DISCOVERY", "PRODUCT_RELEASE"} and len(items) == 2


def test_rss_connector_lobsters(settings):
    it = BY_KEY["lobsters"].fetch(client_for({"lobste.rs": RSS}), settings)[0]
    assert it.description == "Hello world" and it.content_type == "COMMUNITY_DISCUSSION"


def test_google_news_strips_publisher_and_keeps_attribution(settings):
    items = BY_KEY["google_news"].fetch(client_for({"news.google.com": RSS}), settings)
    assert items[0].title == "Startup raises $20M for AI agents" and items[0].publisher == "TechCrunch"
    assert items[0].content_type == "VERIFIED_NEWS"


def test_google_news_url_resolution():
    import base64
    tok = base64.urlsafe_b64encode(b"\x08\x13\x22\x1ehttps://example.com/story-1\xd2\x01\x00").decode().rstrip("=")
    assert resolve_google_news_url(f"https://news.google.com/rss/articles/{tok}?oc=5") == "https://example.com/story-1"
    opaque = "https://news.google.com/rss/articles/CBMiOpaqueXYZ?oc=5"
    assert resolve_google_news_url(opaque) == opaque


def test_restricted_and_paid_sources_are_unavailable_by_default():
    from app.config import Settings
    s = Settings()
    for k in ("techcrunch", "google_news", "sciencedaily", "reddit", "x"):
        ok, why = BY_KEY[k].availability(s)
        assert not ok and why
    assert BY_KEY["reddit"].availability(Settings(reddit_client_id="a", reddit_client_secret="b", reddit_user_agent="u"))[0] is False
    assert BY_KEY["reddit"].availability(Settings(reddit_client_id="a", reddit_client_secret="b", reddit_user_agent="u", reddit_commercial_approved=True))[0]
    assert BY_KEY["x"].availability(Settings(x_enabled=True, x_bearer_token="t"))[0]


def test_reddit_uses_oauth_and_skips_nsfw(settings):
    s = settings.model_copy(update={"reddit_client_id": "a", "reddit_client_secret": "b", "reddit_user_agent": "u",
                                    "reddit_commercial_approved": True, "reddit_subreddits": "programming"})
    c = client_for({"access_token": {"access_token": "T"},
                    "oauth.reddit.com/r/programming/hot": {"data": {"children": [
                        {"data": {"id": "1", "title": "Show: my new tool", "permalink": "/r/programming/1", "created_utc": 1700000000, "score": 5, "num_comments": 2, "author": "x"}},
                        {"data": {"id": "2", "title": "nsfw thing here", "permalink": "/r/programming/2", "created_utc": 1700000000, "over_18": True}}]}}})
    items = BY_KEY["reddit"].fetch(c, s)
    assert len(items) == 1 and items[0].url.startswith("https://www.reddit.com/r/")


def test_x_connector(settings):
    s = settings.model_copy(update={"x_enabled": True, "x_bearer_token": "t"})
    c = client_for({"tweets/search/recent": {"data": [{"id": "9", "text": "New open source model out", "author_id": "1", "created_at": "2026-01-01T00:00:00Z",
                                                       "public_metrics": {"like_count": 4, "reply_count": 1, "retweet_count": 2}}],
                                             "includes": {"users": [{"id": "1", "username": "dev", "name": "Dev"}]}}})
    it = BY_KEY["x"].fetch(c, s)[0]
    assert it.url == "https://x.com/dev/status/9" and it.engagement == 7


# ---- http layer: retry / backoff / rate limit -------------------------------------------------------------
def test_retries_5xx_with_exponential_backoff():
    calls, sleeps = [], []
    def h(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"ok": 1})
    r = fetch(httpx.Client(transport=httpx.MockTransport(h)), "https://x.io", retries=3, backoff=1, sleep=sleeps.append)
    assert r.json() == {"ok": 1} and sleeps == [1, 2]


def test_rate_limit_honours_retry_after_then_gives_up():
    sleeps = []
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"retry-after": "7"})))
    with pytest.raises(RateLimited):
        fetch(c, "https://x.io", retries=2, sleep=sleeps.append)
    assert sleeps == [7, 7]


def test_4xx_not_retried_and_network_errors_retried():
    n = []
    c = httpx.Client(transport=httpx.MockTransport(lambda r: (n.append(1), httpx.Response(404))[1]))
    with pytest.raises(ConnectorError):
        fetch(c, "https://x.io", retries=3, sleep=lambda s: None)
    assert len(n) == 1

    m = []
    def boom(req):
        m.append(1)
        raise httpx.ConnectTimeout("t")
    with pytest.raises(ConnectorError):
        fetch(httpx.Client(transport=httpx.MockTransport(boom)), "https://x.io", retries=2, sleep=lambda s: None)
    assert len(m) == 3
