from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    source_key: str
    external_id: str
    title: str
    url: str
    published_at: datetime | None = None
    author: str | None = None
    publisher: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    content_type: str = "COMMUNITY_DISCUSSION"
    tags: list[str] = field(default_factory=list)
    engagement: float = 0.0     # source-native popularity (score+comments, stars, likes...)


class Connector:
    key = ""
    name = ""
    kind = "api"                  # api | rss | social
    access = "free"               # free | paid | approval_required | terms_restricted
    authority = 50                # who wins "primary source" when several sources find one story (0-100)
    topic_prior = 0.1             # how inherently tech-focused the feed is (added to relevance)
    notes = ""
    default_category: str | None = None

    def availability(self, s) -> tuple[bool, str]:
        """(usable, reason_if_not). Checked before every run."""
        if self.access == "terms_restricted" and not s.enable_terms_restricted_sources:
            return False, "Terms-restricted source: review its current feed terms, then set ENABLE_TERMS_RESTRICTED_SOURCES=true."
        return True, ""

    def fetch(self, client, s) -> list[RawItem]:
        raise NotImplementedError
