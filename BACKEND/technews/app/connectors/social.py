from datetime import datetime, timezone

from app.connectors.base import Connector, RawItem
from app.http import ConnectorError, fetch


class Reddit(Connector):
    key, name, kind, access, authority, topic_prior = "reddit", "Reddit", "social", "approval_required", 20, 0.1
    notes = "Official Data API only (OAuth). Requires approved access; commercial use needs Reddit's approval. Never falls back to scraping."

    def availability(self, s):
        if not (s.reddit_client_id and s.reddit_client_secret and s.reddit_user_agent):
            return False, "Reddit API credentials not configured (REDDIT_CLIENT_ID/SECRET/USER_AGENT)."
        if not s.reddit_commercial_approved:
            return False, "Disabled until REDDIT_COMMERCIAL_APPROVED=true, i.e. you confirm Reddit has approved your use case."
        return True, ""

    def fetch(self, client, s):
        ua = {"User-Agent": s.reddit_user_agent}
        tok = fetch(client, "https://www.reddit.com/api/v1/access_token", method="POST", headers=ua,
                    data={"grant_type": "client_credentials"}, auth=(s.reddit_client_id, s.reddit_client_secret),
                    retries=s.http_retries, backoff=s.http_backoff).json().get("access_token")
        if not tok:
            raise ConnectorError("Reddit did not return an access token")
        h = {**ua, "Authorization": f"Bearer {tok}"}
        out = []
        for sub in s.subreddits:
            r = fetch(client, f"https://oauth.reddit.com/r/{sub}/hot", headers=h, params={"limit": 25},
                      retries=s.http_retries, backoff=s.http_backoff)
            for c in r.json().get("data", {}).get("children", []):
                d = c.get("data", {})
                if d.get("over_18") or d.get("stickied") or d.get("removed_by_category") or not d.get("title"):
                    continue
                out.append(RawItem(
                    self.key, d["id"], d["title"], "https://www.reddit.com" + d["permalink"],
                    published_at=datetime.fromtimestamp(d["created_utc"], tz=timezone.utc),
                    author=d.get("author"), publisher=f"r/{sub}", tags=[f"r-{sub.lower()}"],
                    engagement=float(d.get("score", 0) + d.get("num_comments", 0)),
                ))
        return out


class XTwitter(Connector):
    key, name, kind, access, authority, topic_prior = "x", "X (Twitter)", "social", "paid", 20, 0.1
    notes = "Official X API v2 recent search. Search requires a paid API tier; check current pricing and terms."

    def availability(self, s):
        if not s.x_enabled:
            return False, "Disabled (X_ENABLED=false). X search requires paid API access."
        if not s.x_bearer_token:
            return False, "X_BEARER_TOKEN not configured."
        return True, ""

    def fetch(self, client, s):
        r = fetch(client, "https://api.x.com/2/tweets/search/recent",
                  headers={"Authorization": f"Bearer {s.x_bearer_token}"},
                  params={"query": s.x_query, "max_results": 50, "tweet.fields": "created_at,public_metrics",
                          "expansions": "author_id", "user.fields": "username,name"},
                  retries=s.http_retries, backoff=s.http_backoff).json()
        users = {u["id"]: u for u in r.get("includes", {}).get("users", [])}
        out = []
        for t in r.get("data", []):
            u = users.get(t.get("author_id"), {})
            m = t.get("public_metrics", {})
            out.append(RawItem(
                self.key, t["id"], t["text"].replace("\n", " ")[:200],
                f"https://x.com/{u.get('username', 'i')}/status/{t['id']}",
                published_at=datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")) if t.get("created_at") else None,
                author=u.get("name"), publisher=f"@{u['username']}" if u.get("username") else "X",
                engagement=float(m.get("like_count", 0) + m.get("reply_count", 0) + m.get("retweet_count", 0)),
            ))
        return out
