from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_user
from app.database.models import Domain, Match, MatchPlayer, PlayerStats, PointsTransaction, User
from app.database.session import get_session

router = APIRouter(prefix="/api/v1/players/me", tags=["players"])


async def _stats(s, uid) -> PlayerStats:
    return (await s.execute(select(PlayerStats).where(PlayerStats.user_id == uid))).scalar_one()


@router.get("/stats")
async def stats(s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    p = await _stats(s, u.id)
    answered = p.total_correct + p.total_incorrect
    return {"matches_played": p.matches_played, "wins": p.wins, "losses": p.losses, "draws": p.draws,
            "win_rate": round(p.wins / p.matches_played * 100, 2) if p.matches_played else 0,
            "average_accuracy": p.average_accuracy, "highest_accuracy": p.highest_accuracy,
            "total_correct": p.total_correct, "total_incorrect": p.total_incorrect, "total_answered": answered,
            "total_points": p.total_points, "current_streak": p.current_streak, "longest_streak": p.longest_streak,
            "best_match_score": p.best_match_score, "rating": p.rating}


@router.get("/points")
async def points(s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    return {"total_points": (await _stats(s, u.id)).total_points}


@router.get("/points/history")
async def points_history(limit: int = Query(20, le=100), offset: int = 0, s: AsyncSession = Depends(get_session),
                         u: User = Depends(current_user)):
    rows = (await s.execute(select(PointsTransaction).where(PointsTransaction.user_id == u.id)
                            .order_by(PointsTransaction.created_at.desc()).limit(limit).offset(offset))).scalars()
    return [{"id": t.id, "source_type": t.source_type, "source_id": t.source_id, "type": t.transaction_type,
             "points": t.points, "created_at": t.created_at.isoformat()} for t in rows]


@router.get("/activity")
async def activity(limit: int = Query(20, le=100), offset: int = 0, domain_id: str | None = None,
                   game_mode: str | None = None, result: str | None = Query(None, pattern="^(WIN|LOSS|DRAW)$"),
                   s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    st = (select(MatchPlayer, Match, Domain).join(Match, Match.id == MatchPlayer.match_id)
          .join(Domain, Domain.id == Match.domain_id)
          .where(MatchPlayer.user_id == u.id, Match.status == "COMPLETED"))
    if domain_id:
        st = st.where(Match.domain_id == domain_id)
    if game_mode:
        st = st.where(Match.game_mode == game_mode)
    if result:
        st = st.where(MatchPlayer.result == result)
    total = (await s.execute(select(func.count()).select_from(st.subquery()))).scalar_one()
    rows = (await s.execute(st.order_by(Match.ended_at.desc()).limit(limit).offset(offset))).all()
    items = []
    for mp, m, d in rows:
        opp = (await s.execute(select(MatchPlayer, User).join(User, User.id == MatchPlayer.user_id)
                               .where(MatchPlayer.match_id == m.id, MatchPlayer.user_id != u.id))).first()
        items.append({"match_id": m.id, "opponent": {"user_id": opp[1].id, "display_name": opp[1].display_name,
                                                     "avatar_url": opp[1].avatar_url} if opp else None,
                      "game_mode": m.game_mode, "domain": d.name, "duration_seconds": m.duration_seconds,
                      "result": mp.result, "score": mp.final_score, "opponent_score": opp[0].final_score if opp else None,
                      "accuracy": mp.accuracy, "correct": mp.correct_answers, "incorrect": mp.incorrect_answers,
                      "unanswered": mp.unanswered, "points_earned": mp.points_earned,
                      "completed_at": m.ended_at.isoformat() if m.ended_at else None})
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/performance")
async def performance(s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    """Best performance rule: highest accuracy among completed matches with >=5 answered; ties -> higher score."""
    p = await _stats(s, u.id)
    rows = (await s.execute(select(MatchPlayer, Match, Domain).join(Match, Match.id == MatchPlayer.match_id)
                            .join(Domain, Domain.id == Match.domain_id)
                            .where(MatchPlayer.user_id == u.id, Match.status == "COMPLETED"))).all()
    elig = [r for r in rows if r[0].correct_answers + r[0].incorrect_answers >= 5]
    best = max(elig, key=lambda r: (r[0].accuracy, r[0].final_score), default=None)
    per_domain: dict[str, list[float]] = {}
    for mp, _, d in rows:
        per_domain.setdefault(d.name, []).append(mp.accuracy)
    avg = {k: sum(v) / len(v) for k, v in per_domain.items()}
    return {"wins": p.wins, "losses": p.losses, "average_accuracy": p.average_accuracy,
            "best_performance": None if not best else {"accuracy": best[0].accuracy, "domain": best[2].name,
                                                       "game_mode": best[1].game_mode, "score": best[0].final_score},
            "best_domain": max(avg, key=avg.get) if avg else None,
            "weakest_domain": min(avg, key=avg.get) if avg else None}
