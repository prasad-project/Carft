import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DEFAULT_RULES
from app.core.redis import get_redis, get_rules
from app.core.security import ArenaError, admin_user
from app.database.models import Domain, Match, Question, User
from app.database.session import get_session
from app.services import question_service as qs

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class Option(BaseModel):
    id: str
    text: str


class QuestionIn(BaseModel):
    domain_id: str
    subdomain_id: str | None = None
    question_text: str
    question_type: str = "CONCEPTUAL"
    code_snippet: str | None = None
    options: list[Option]
    correct_option: str
    explanation: str = ""
    difficulty: str = "MEDIUM"
    topic: str | None = None
    source: str | None = None
    status: str = "DRAFT"
    tags: list[str] = []


class QuestionPatch(BaseModel):
    question_text: str | None = None
    code_snippet: str | None = None
    options: list[Option] | None = None
    correct_option: str | None = None
    explanation: str | None = None
    difficulty: str | None = None
    topic: str | None = None
    status: str | None = None


class DomainIn(BaseModel):
    name: str
    slug: str
    description: str = ""
    parent_id: str | None = None
    icon: str | None = None


def dump(m: QuestionIn) -> dict:
    d = m.model_dump()
    d["options"] = [o for o in d["options"]]
    return d


@router.post("/domains", status_code=201)
async def create_domain(b: DomainIn, s: AsyncSession = Depends(get_session), _: User = Depends(admin_user)):
    if (await s.execute(select(Domain.id).where(Domain.slug == b.slug))).first():
        raise ArenaError("DUPLICATE", "Slug exists", 409)
    d = Domain(**b.model_dump())
    s.add(d)
    await s.commit()
    return {"id": d.id}


@router.post("/questions", status_code=201)
async def create_question(b: QuestionIn, s: AsyncSession = Depends(get_session), a: User = Depends(admin_user)):
    q = await qs.create_question(s, dump(b), a.id)
    await s.commit()
    return {"id": q.id, "status": q.status}


@router.get("/questions")
async def list_questions(domain_id: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0,
                         s: AsyncSession = Depends(get_session), _: User = Depends(admin_user)):
    st = select(Question).order_by(Question.created_at.desc()).limit(min(limit, 200)).offset(offset)
    if domain_id:
        st = st.where(Question.domain_id == domain_id)
    if status:
        st = st.where(Question.status == status)
    return [{"id": q.id, "domain_id": q.domain_id, "question_text": q.question_text, "options": q.options,
             "correct_option": q.correct_option, "explanation": q.explanation, "difficulty": q.difficulty,
             "status": q.status} for q in (await s.execute(st)).scalars()]


@router.patch("/questions/{qid}")
async def patch_question(qid: str, b: QuestionPatch, s: AsyncSession = Depends(get_session),
                         _: User = Depends(admin_user)):
    q = await s.get(Question, qid)
    if not q:
        raise ArenaError("NOT_FOUND", "Question not found", 404)
    await qs.update_question(s, q, b.model_dump(exclude_unset=True))
    await s.commit()
    return {"id": q.id, "status": q.status}


@router.delete("/questions/{qid}")
async def archive_question(qid: str, s: AsyncSession = Depends(get_session), _: User = Depends(admin_user)):
    q = await s.get(Question, qid)
    if not q:
        raise ArenaError("NOT_FOUND", "Question not found", 404)
    q.status = "ARCHIVED"
    await s.commit()
    return {"id": q.id, "status": q.status}


@router.post("/questions/import")
async def import_questions(items: list[QuestionIn], s: AsyncSession = Depends(get_session),
                           a: User = Depends(admin_user)):
    ok, errors = 0, []
    for i, it in enumerate(items):
        try:
            async with s.begin_nested():
                await qs.create_question(s, dump(it), a.id)
            ok += 1
        except ArenaError as e:
            errors.append({"index": i, "code": e.code, "message": e.message})
    await s.commit()
    return {"imported": ok, "errors": errors}


class Rules(BaseModel):
    base_points: int | None = Field(None, ge=0)
    max_speed_bonus: int | None = Field(None, ge=0)
    reward_win: int | None = Field(None, ge=0)
    reward_loss: int | None = Field(None, ge=0)
    reward_draw: int | None = Field(None, ge=0)
    reveal_pause_ms: int | None = Field(None, ge=0, le=3000)


@router.get("/rules")
async def get_rules_ep(_: User = Depends(admin_user)):
    return await get_rules()


@router.put("/rules")
async def put_rules(b: Rules, _: User = Depends(admin_user)):
    upd = {k: json.dumps(v) for k, v in b.model_dump(exclude_none=True).items() if k in DEFAULT_RULES}
    if upd:
        await get_redis().hset("arena:rules", mapping=upd)
    return await get_rules()


@router.get("/analytics")
async def analytics(s: AsyncSession = Depends(get_session), _: User = Depends(admin_user)):
    by_status = dict((await s.execute(select(Match.status, func.count()).group_by(Match.status))).all())
    q = dict((await s.execute(select(Question.status, func.count()).group_by(Question.status))).all())
    users = (await s.execute(select(func.count()).select_from(User))).scalar_one()
    return {"users": users, "matches_by_status": by_status, "questions_by_status": q}
