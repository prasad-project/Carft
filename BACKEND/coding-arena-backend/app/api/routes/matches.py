from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ArenaError, current_user
from app.database.models import Domain, Match, MatchPlayer, User
from app.database.session import get_session
from app.game import engine

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


async def _load(s: AsyncSession, mid: str, user: User):
    m = await s.get(Match, mid)
    mps = list((await s.execute(select(MatchPlayer).where(MatchPlayer.match_id == mid))).scalars()) if m else []
    if not m or user.id not in [p.user_id for p in mps]:  # 404 for outsiders: don't leak existence
        raise ArenaError("NOT_FOUND", "Match not found", 404)
    return m, mps


async def _players(s, mps):
    us = {u.id: u for u in (await s.execute(select(User).where(User.id.in_([p.user_id for p in mps])))).scalars()}
    return [{"user_id": p.user_id, "display_name": us[p.user_id].display_name, "avatar_url": us[p.user_id].avatar_url,
             "final_score": p.final_score, "correct": p.correct_answers, "incorrect": p.incorrect_answers,
             "unanswered": p.unanswered, "accuracy": p.accuracy, "avg_response_ms": p.average_response_time,
             "speed_bonus": p.speed_bonus, "result": p.result, "points_earned": p.points_earned} for p in mps]


@router.get("/{match_id}")
async def state(match_id: str, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    m, mps = await _load(s, match_id, u)
    out = {"match_id": m.id, "room_id": m.room_id, "status": m.status, "game_mode": m.game_mode,
           "domain_id": m.domain_id, "duration_seconds": m.duration_seconds, "question_count": m.question_count}
    if m.status in ("STARTING", "IN_PROGRESS"):
        try:
            out["live"] = await engine.snapshot(m.id, u.id)
        except ArenaError:
            pass
    return out


@router.get("/{match_id}/results")
async def results(match_id: str, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    m, mps = await _load(s, match_id, u)
    if m.status != "COMPLETED":
        raise ArenaError("NOT_COMPLETED", "Match has no final results yet", 409)
    d = await s.get(Domain, m.domain_id)
    return {"match_id": m.id, "domain": d.name, "game_mode": m.game_mode, "duration_seconds": m.duration_seconds,
            "winner_id": m.winner_id, "is_draw": m.winner_id is None, "end_reason": m.end_reason,
            "ended_at": m.ended_at.isoformat() if m.ended_at else None, "players": await _players(s, mps)}


@router.get("/{match_id}/history")
async def history(match_id: str, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    return await results(match_id, s, u)
