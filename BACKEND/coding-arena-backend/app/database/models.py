import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


def utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


def pk():
    return mapped_column(String(32), primary_key=True, default=uid)


def ts(**kw):
    return mapped_column(DateTime(timezone=True), **kw)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = pk()
    username: Mapped[str] = mapped_column(String(40), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = ts(default=now)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    role: Mapped[str] = mapped_column(String(20), default="ADMIN")
    created_at: Mapped[datetime] = ts(default=now)


class PlayerStats(Base):
    __tablename__ = "player_stats"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    average_accuracy: Mapped[float] = mapped_column(Float, default=0)
    highest_accuracy: Mapped[float] = mapped_column(Float, default=0)
    total_correct: Mapped[int] = mapped_column(Integer, default=0)
    total_incorrect: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_match_score: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=1000)
    updated_at: Mapped[datetime] = ts(default=now, onupdate=now)


class Domain(Base):
    __tablename__ = "domains"
    id: Mapped[str] = pk()
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("domains.id", ondelete="SET NULL"), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty in ('EASY','MEDIUM','HARD')", name="ck_q_difficulty"),
        CheckConstraint("status in ('DRAFT','REVIEW','PUBLISHED','ARCHIVED')", name="ck_q_status"),
        CheckConstraint("correct_option in ('A','B','C','D')", name="ck_q_correct"),
        Index("ix_q_domain_status", "domain_id", "status"),
    )
    id: Mapped[str] = pk()
    domain_id: Mapped[str] = mapped_column(ForeignKey("domains.id"))
    subdomain_id: Mapped[str | None] = mapped_column(ForeignKey("domains.id"), nullable=True)
    question_text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(30), default="CONCEPTUAL")
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list] = mapped_column(JSON)  # [{"id":"A","text":"..."}, ... x4]
    correct_option: Mapped[str] = mapped_column(String(1))
    explanation: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(10), default="MEDIUM")
    topic: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text_hash: Mapped[str] = mapped_column(String(64), unique=True)  # duplicate-question guard
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = ts(default=now)
    updated_at: Mapped[datetime] = ts(default=now, onupdate=now)


class QuestionTag(Base):
    __tablename__ = "question_tags"
    __table_args__ = (UniqueConstraint("question_id", "tag"),)
    id: Mapped[str] = pk()
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    tag: Mapped[str] = mapped_column(String(40))


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (CheckConstraint("duration_seconds > 0", name="ck_room_dur"),)
    id: Mapped[str] = pk()
    room_code: Mapped[str] = mapped_column(String(8), unique=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    domain_id: Mapped[str] = mapped_column(ForeignKey("domains.id"))
    duration_seconds: Mapped[int] = mapped_column(Integer)
    question_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(15), default="WAITING", index=True)
    expires_at: Mapped[datetime] = ts()
    created_at: Mapped[datetime] = ts(default=now)


class RoomPlayer(Base):
    __tablename__ = "room_players"
    __table_args__ = (UniqueConstraint("room_id", "user_id"),)
    id: Mapped[str] = pk()
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = ts(default=now)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[str] = pk()
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    game_mode: Mapped[str] = mapped_column(String(20), default="PRIVATE_ROOM")
    domain_id: Mapped[str] = mapped_column(ForeignKey("domains.id"))
    duration_seconds: Mapped[int] = mapped_column(Integer)
    question_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(15), default="STARTING", index=True)
    started_at: Mapped[datetime | None] = ts(nullable=True)
    ended_at: Mapped[datetime | None] = ts(nullable=True)
    winner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = ts(default=now)


class MatchPlayer(Base):
    __tablename__ = "match_players"
    __table_args__ = (UniqueConstraint("match_id", "user_id"), Index("ix_mp_user", "user_id"))
    id: Mapped[str] = pk()
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    final_score: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_answers: Mapped[int] = mapped_column(Integer, default=0)
    unanswered: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0)
    average_response_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_bonus: Mapped[int] = mapped_column(Integer, default=0)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(String(5), nullable=True)  # WIN/LOSS/DRAW


class MatchQuestion(Base):
    __tablename__ = "match_questions"
    __table_args__ = (UniqueConstraint("match_id", "question_order"),)
    id: Mapped[str] = pk()
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    question_order: Mapped[int] = mapped_column(Integer)
    activated_at: Mapped[datetime | None] = ts(nullable=True)
    deadline_at: Mapped[datetime | None] = ts(nullable=True)


class MatchAnswer(Base):
    __tablename__ = "match_answers"
    __table_args__ = (UniqueConstraint("match_id", "question_id", "user_id", name="uq_one_answer"),)
    id: Mapped[str] = pk()
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    selected_option: Mapped[str] = mapped_column(String(1))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    response_time_ms: Mapped[int] = mapped_column(Integer)
    points_awarded: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = ts()


class PointsTransaction(Base):
    __tablename__ = "points_transactions"
    __table_args__ = (UniqueConstraint("user_id", "source_type", "source_id", "transaction_type", name="uq_reward_once"),
                      Index("ix_pt_user_created", "user_id", "created_at"))
    id: Mapped[str] = pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(32))
    transaction_type: Mapped[str] = mapped_column(String(20))
    points: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = ts(default=now)
