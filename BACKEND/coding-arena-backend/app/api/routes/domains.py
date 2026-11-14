from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ArenaError, current_user
from app.database.models import Domain, Question, User
from app.database.session import get_session
from app.services.question_service import pool_size

router = APIRouter(prefix="/api/v1/domains", tags=["domains"])


@router.get("")
async def list_domains(s: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    counts = dict((await s.execute(select(Question.domain_id, func.count()).where(Question.status == "PUBLISHED")
                                   .group_by(Question.domain_id))).all())
    rows = (await s.execute(select(Domain).where(Domain.is_active).order_by(Domain.name))).scalars().all()
    return [{"id": d.id, "name": d.name, "slug": d.slug, "description": d.description, "parent_id": d.parent_id,
             "icon": d.icon, "is_active": d.is_active, "available_questions": counts.get(d.id, 0)} for d in rows]


@router.get("/{domain_id}/questions/count")
async def question_count(domain_id: str, s: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    if not await s.get(Domain, domain_id):
        raise ArenaError("NOT_FOUND", "Domain not found", 404)
    return {"domain_id": domain_id, "published": await pool_size(s, domain_id)}
