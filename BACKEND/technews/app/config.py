from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/technews"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    viewer_hash_secret: str = "change-me-too"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"
    sentry_dsn: str = ""
    rate_limit_default: str = "120/minute"
    rate_limit_storage: str = ""   # defaults to redis_url

    timezone: str = "Asia/Kolkata"
    ingest_hours: str = "0,8,16"

    http_timeout: float = 15.0
    http_retries: int = 3
    http_backoff: float = 1.0
    user_agent: str = "TechNewsPortfolioBot/1.0 (+contact: set-your-email@example.com)"

    hn_per_feed: int = 25
    github_token: str = ""
    github_watch_repos: str = (
        "pytorch/pytorch,huggingface/transformers,vercel/next.js,facebook/react,"
        "python/cpython,rust-lang/rust,kubernetes/kubernetes,tiangolo/fastapi"
    )
    devto_per_page: int = 30
    arxiv_max_results: int = 30
    hf_limit: int = 25

    enable_terms_restricted_sources: bool = False
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = ""
    reddit_commercial_approved: bool = False
    reddit_subreddits: str = "technology,programming,artificial,MachineLearning,datascience,LocalLLaMA,startups,webdev"
    x_enabled: bool = False
    x_bearer_token: str = ""
    x_query: str = '("new AI model" OR "open source" OR "startup launch" OR "developer tools") -is:retweet lang:en'

    show_third_party_thumbnails: bool = False
    auto_publish: bool = True
    min_relevance: float = 0.2

    dedupe_title_ratio: float = 0.88
    dedupe_jaccard: float = 0.7
    dedupe_window_hours: int = 72

    # Ranking (configurable). Spec weights; w_external defaults to 0 -> see README on cold start.
    w_views: float = 0.35
    w_likes: float = 0.30
    w_comments: float = 0.20
    w_fresh_rel: float = 0.15
    w_external: float = 0.0
    rank_window_days: int = 7
    freshness_half_life_hours: float = 36.0
    trending_half_life_hours: float = 72.0
    min_view_dwell_seconds: int = 5

    ai_enabled: bool = False
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""

    @property
    def watch_repos(self) -> list[str]:
        return [r.strip() for r in self.github_watch_repos.split(",") if r.strip()]

    @property
    def subreddits(self) -> list[str]:
        return [r.strip() for r in self.reddit_subreddits.split(",") if r.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
