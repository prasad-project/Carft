import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import feedparser

from app.connectors.base import Connector, RawItem
from app.http import ConnectorError, fetch
from app.util import parse_iso, strip_html, utcnow

log = logging.getLogger(__name__)


def _get(client, s, url, **kw):
    return fetch(client, url, retries=s.http_retries, backoff=s.http_backoff, **kw)


class HackerNews(Connector):
    key, name, kind, access, authority, topic_prior = "hackernews", "Hacker News", "api", "free", 40, 0.1
    FEEDS = {"top": "topstories", "best": "beststories", "new": "newstories", "show": "showstories", "ask": "askstories"}
    BASE = "https://hacker-news.firebaseio.com/v0"

    def fetch(self, client, s):
        ids: dict[int, str] = {}
        for feed, ep in self.FEEDS.items():
            for i in _get(client, s, f"{self.BASE}/{ep}.json").json()[: s.hn_per_feed]:
                ids.setdefault(i, feed)

        def one(i):
            try:
                return _get(client, s, f"{self.BASE}/item/{i}.json").json()
            except ConnectorError:
                return None

        with ThreadPoolExecutor(max_workers=8) as ex:
            raw = list(ex.map(one, ids))
        out = []
        for it in raw:
            if not it or it.get("type") != "story" or it.get("dead") or it.get("deleted") or not it.get("title"):
                continue
            url = it.get("url") or f"https://news.ycombinator.com/item?id={it['id']}"
            host = urlsplit(url).hostname or "news.ycombinator.com"
            out.append(RawItem(
                self.key, str(it["id"]), it["title"], url,
                published_at=datetime.fromtimestamp(it["time"], tz=timezone.utc),
                author=it.get("by"), publisher=host.removeprefix("www."),
                tags=[ids[it["id"]] + "-hn"], engagement=float(it.get("score", 0) + it.get("descendants", 0)),
            ))
        return out


class GitHub(Connector):
    key, name, kind, access, authority, topic_prior = "github", "GitHub", "api", "free", 70, 0.4
    notes = "Optional GITHUB_TOKEN raises rate limit from 60/h to 5000/h. 'Trending' is approximated via recent repos sorted by stars; GitHub has no official trending API."
    default_category = "open-source"

    def fetch(self, client, s):
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if s.github_token:
            h["Authorization"] = f"Bearer {s.github_token}"
        out: list[RawItem] = []
        since = (utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        r = _get(client, s, "https://api.github.com/search/repositories", headers=h,
                 params={"q": f"created:>{since} stars:>50", "sort": "stars", "order": "desc", "per_page": 30})
        for repo in r.json().get("items", []):
            desc = (repo.get("description") or "")[:200]
            out.append(RawItem(
                self.key, f"repo:{repo['id']}", f"{repo['full_name']}: {desc}".strip(": "), repo["html_url"],
                published_at=parse_iso(repo.get("created_at")), author=repo["owner"]["login"], publisher="GitHub",
                description=desc, content_type="DEVELOPER_DISCOVERY",
                tags=[t for t in [repo.get("language"), *(repo.get("topics") or [])[:4]] if t],
                engagement=float(repo.get("stargazers_count", 0)),
            ))
        for repo in s.watch_repos:
            try:
                rels = _get(client, s, f"https://api.github.com/repos/{repo}/releases", headers=h, params={"per_page": 3}).json()
            except ConnectorError as e:
                log.warning("github_release_fetch_failed", extra={"repo": repo, "error": str(e)})
                continue
            for rel in rels:
                if rel.get("draft") or rel.get("prerelease"):
                    continue
                out.append(RawItem(
                    self.key, f"release:{rel['id']}", f"{repo} {rel.get('name') or rel['tag_name']} released", rel["html_url"],
                    published_at=parse_iso(rel.get("published_at")), author=(rel.get("author") or {}).get("login"),
                    publisher="GitHub", content_type="PRODUCT_RELEASE", tags=["release", repo.split("/")[-1]],
                ))
        return out


class DevTo(Connector):
    key, name, kind, access, authority, topic_prior = "devto", "DEV Community", "api", "free", 55, 0.4
    notes = "Only title/description/link are stored; article bodies belong to their authors."

    def fetch(self, client, s):
        r = _get(client, s, "https://dev.to/api/articles", params={"per_page": s.devto_per_page, "top": 1})
        out = []
        for a in r.json():
            tags = a.get("tag_list") or []
            tags = tags if isinstance(tags, list) else [t.strip() for t in tags.split(",") if t.strip()]
            out.append(RawItem(
                self.key, str(a["id"]), a["title"], a.get("canonical_url") or a["url"],
                published_at=parse_iso(a.get("published_at") or a.get("published_timestamp")),
                author=(a.get("user") or {}).get("name"), publisher="DEV Community",
                description=strip_html(a.get("description"), 300), thumbnail=a.get("cover_image") or a.get("social_image"),
                content_type="DEVELOPER_DISCOVERY", tags=tags[:5],
                engagement=float(a.get("positive_reactions_count", 0) + a.get("comments_count", 0)),
            ))
        return out


class Arxiv(Connector):
    key, name, kind, access, authority, topic_prior = "arxiv", "arXiv", "api", "free", 70, 0.4
    notes = "arXiv asks for ≤1 request / 3s; this connector makes one request per run."
    default_category = "research"

    def fetch(self, client, s):
        r = _get(client, s, "https://export.arxiv.org/api/query", params={
            "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.RO OR cat:cs.CR",
            "sortBy": "submittedDate", "sortOrder": "descending", "max_results": s.arxiv_max_results})
        out = []
        for e in feedparser.parse(r.content).entries:
            pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc) if e.get("published_parsed") else None
            out.append(RawItem(
                self.key, e.id, re.sub(r"\s+", " ", e.title).strip(), e.link, published_at=pub,
                author=", ".join(a.name for a in e.get("authors", [])[:3]) or None, publisher="arXiv",
                description=strip_html(e.get("summary"), 400), content_type="RESEARCH_UPDATE",
                tags=[t["term"] for t in e.get("tags", [])][:4],
            ))
        return out


class HuggingFace(Connector):
    key, name, kind, access, authority, topic_prior = "huggingface", "Hugging Face", "api", "free", 65, 0.5
    notes = "Uses the public Hub API (no token needed for public listings)."
    default_category = "machine-learning"

    def fetch(self, client, s):
        out = []
        for kind, path in (("model", "models"), ("dataset", "datasets")):
            r = _get(client, s, f"https://huggingface.co/api/{path}",
                     params={"sort": "trendingScore", "direction": -1, "limit": s.hf_limit})
            for m in r.json():
                mid = m.get("id") or m.get("modelId")
                if not mid:
                    continue
                url = f"https://huggingface.co/{'datasets/' if kind == 'dataset' else ''}{mid}"
                label = m.get("pipeline_tag") or kind
                out.append(RawItem(
                    self.key, f"{kind}:{mid}", f"{mid} — trending {label} on Hugging Face", url,
                    published_at=parse_iso(m.get("createdAt")) or parse_iso(m.get("lastModified")),
                    author=mid.split("/")[0], publisher="Hugging Face", content_type="DEVELOPER_DISCOVERY",
                    tags=[t for t in (m.get("tags") or []) if ":" not in t][:4] + [kind],
                    engagement=float(m.get("likes", 0)),
                ))
        return out
