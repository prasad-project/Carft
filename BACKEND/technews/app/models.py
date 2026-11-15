from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.util import utcnow


class Base(DeclarativeBase):
    pass


def _ts():
    return mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    """MINIMAL STUB. Map this to your existing users table (same table name/PK) and delete this class."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Category(Base):
    __tablename__ = "news_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80))


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(60))


article_tags = Table(
    "article_tags", Base.metadata,
    Column("article_id", ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class NewsSource(Base):
    """Connector registry + status + non-secret config. Secrets live in env vars only."""
    __tablename__ = "news_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))            # api | rss | social
    access: Mapped[str] = mapped_column(String(30))          # free | paid | approval_required | terms_restricted
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_weight: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), default="never_run")  # ok | error | unavailable | never_run
    status_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict | None] = mapped_column(JSON, default=dict)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Article(Base):
    __tablename__ = "news_articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    title_norm: Mapped[str] = mapped_column(String(500), index=True)
    source_key: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(20))
    original_url: Mapped[str] = mapped_column(String(2048))
    canonical_url: Mapped[str] = mapped_column(String(2048), index=True)
    author_name: Mapped[str | None] = mapped_column(String(200))
    publisher_name: Mapped[str | None] = mapped_column(String(200))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_is_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(ForeignKey("news_categories.slug"))
    content_type: Mapped[str] = mapped_column(String(30))
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    popularity_score: Mapped[float] = mapped_column(Float, default=0.0)
    trending_score: Mapped[float] = mapped_column(Float, default=0.0)
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|published|rejected|archived
    review_reason: Mapped[str | None] = mapped_column(Text)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_trending: Mapped[bool] = mapped_column(Boolean, default=False)   # editorial flag only
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)     # admin edits are never overwritten
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    fetched_at: Mapped[datetime] = _ts()
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    tags: Mapped[list[Tag]] = relationship(secondary=article_tags, lazy="selectin")
    sources: Mapped[list["ArticleSource"]] = relationship(lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_articles_status_pub", "status", "published_at"),)


class ArticleSource(Base):
    __tablename__ = "article_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), index=True)
    source_key: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(2048))
    publisher_name: Mapped[str | None] = mapped_column(String(200))
    metrics: Mapped[dict | None] = mapped_column(JSON, default=dict)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime] = _ts()
    __table_args__ = (UniqueConstraint("source_key", "external_id", name="uq_source_external"),)


class ArticleLike(Base):
    __tablename__ = "article_likes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = _ts()
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_like_user_article"),)


class SavedArticle(Base):
    __tablename__ = "saved_articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = _ts()
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_saved_user_article"),)


class ArticleComment(Base):
    __tablename__ = "article_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ArticleView(Base):
    """One qualified view per (viewer, article, day)."""
    __tablename__ = "article_views"
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), index=True)
    viewer_key: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    day: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts()
    __table_args__ = (UniqueConstraint("article_id", "viewer_key", "day", name="uq_view_viewer_day"),)


class ArticleRanking(Base):
    __tablename__ = "article_rankings"
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True)
    views_7d: Mapped[int] = mapped_column(Integer, default=0)
    likes_7d: Mapped[int] = mapped_column(Integer, default=0)
    comments_7d: Mapped[int] = mapped_column(Integer, default=0)
    editorial_score: Mapped[float] = mapped_column(Float, default=0.0)
    community_score: Mapped[float] = mapped_column(Float, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.0)
    trending_score: Mapped[float] = mapped_column(Float, default=0.0)
    computed_at: Mapped[datetime] = _ts()


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(String(20))   # schedule | manual
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|success|partial|failed|skipped
    source_keys: Mapped[list | None] = mapped_column(JSON)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _ts()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    logs: Mapped[list["IngestionLog"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), index=True)
    source_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))    # success | failed | skipped
    started_at: Mapped[datetime] = _ts()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    saved: Mapped[int] = mapped_column(Integer, default=0)
    duplicated: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "admin_audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(60))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _ts()
