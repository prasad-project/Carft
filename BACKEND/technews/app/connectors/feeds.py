import base64
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

from app.connectors.base import Connector, RawItem
from app.http import fetch
from app.util import strip_html


def _dt(e):
    t = e.get("published_parsed") or e.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


def _thumb(e):
    for k in ("media_thumbnail", "media_content"):
        v = e.get(k)
        if v and v[0].get("url"):
            return v[0]["url"]
    return None


class RssConnector(Connector):
    kind = "rss"
    content_type = "COMMUNITY_DISCUSSION"
    feeds: list[tuple[str, str]] = []     # (url, tag)

    def feed_urls(self, s) -> list[tuple[str, str]]:
        return self.feeds

    def parse_entry(self, e, tag, s) -> RawItem | None:
        if not e.get("link") or not e.get("title"):
            return None
        return RawItem(
            self.key, e.get("id") or e.link, strip_html(e.title), e.link, published_at=_dt(e),
            author=e.get("author"), publisher=self.name, description=strip_html(e.get("summary"), 300),
            thumbnail=_thumb(e), content_type=self.content_type, tags=[tag] if tag else [],
        )

    def fetch(self, client, s):
        out = []
        for url, tag in self.feed_urls(s):
            r = fetch(client, url, retries=s.http_retries, backoff=s.http_backoff)
            for e in feedparser.parse(r.content).entries:
                item = self.parse_entry(e, tag, s)
                if item:
                    out.append(item)
        return out


class Lobsters(RssConnector):
    key, name, access, authority, topic_prior = "lobsters", "Lobsters", "free", 40, 0.3
    feeds = [("https://lobste.rs/rss", ""), ("https://lobste.rs/t/security.rss", "security")]


class ScienceDaily(RssConnector):
    key, name, access, authority, topic_prior = "sciencedaily", "ScienceDaily", "terms_restricted", 85, 0.1
    content_type = "VERIFIED_NEWS"
    notes = "ScienceDaily's feed terms limit reuse; verify before enabling."
    feeds = [("https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml", "ai"),
             ("https://www.sciencedaily.com/rss/computers_math/computer_science.xml", "computer-science")]


class TechCrunch(RssConnector):
    key, name, access, authority, topic_prior = "techcrunch", "TechCrunch", "terms_restricted", 90, 0.2
    content_type = "VERIFIED_NEWS"
    notes = "Headline + link + short feed snippet only. Verify TechCrunch's current feed terms before enabling."
    feeds = [("https://techcrunch.com/feed/", "")]


GN_TOPICS = {
    "Artificial Intelligence": "artificial intelligence", "Generative AI": "generative AI",
    "Machine Learning": "machine learning", "Data Science": "data science", "Startups": "tech startups",
    "Cybersecurity": "cybersecurity", "Software Development": "software development",
    "Cloud Computing": "cloud computing", "Robotics": "robotics", "Indian Technology News": "India technology",
}
_URL_RE = re.compile(rb"https?://[^\s\x00-\x1f\"<>]+")


def resolve_google_news_url(link: str) -> str:
    """Best-effort. Only legacy-format links embed the publisher URL; newer ones are opaque and we keep
    the news.google.com link (which redirects to the publisher). No unofficial decoding endpoints are used."""
    try:
        token = link.split("/articles/")[1].split("?")[0]
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        m = _URL_RE.search(raw)
        if m:
            return m.group(0).decode("utf-8", "ignore")
    except Exception:
        pass
    return link


class GoogleNews(RssConnector):
    key, name, access, authority, topic_prior = "google_news", "Google News", "terms_restricted", 80, 0.2
    content_type = "VERIFIED_NEWS"
    notes = "Discovery only: stores headline, publisher, time and link. Most links cannot be resolved to the publisher URL without unofficial decoding, so they remain news.google.com redirects."

    def feed_urls(self, s):
        return [(f"https://news.google.com/rss/search?q={quote_plus(q + ' when:2d')}&hl=en-IN&gl=IN&ceid=IN:en", topic)
                for topic, q in GN_TOPICS.items()]

    def parse_entry(self, e, tag, s):
        if not e.get("link") or not e.get("title"):
            return None
        publisher = (e.get("source") or {}).get("title")
        title = strip_html(e.title)
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3]
        return RawItem(
            self.key, e.get("id") or e.link, title, resolve_google_news_url(e.link), published_at=_dt(e),
            publisher=publisher or "Google News", content_type=self.content_type, tags=[tag],
        )
