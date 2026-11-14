import hashlib
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ArenaError
from app.database.models import Domain, Question, QuestionTag

DIFFS = ("EASY", "MEDIUM", "HARD")
QTYPES = ("CONCEPTUAL", "PREDICT_OUTPUT", "SYNTAX", "IDENTIFY_CODE", "FIND_ERROR", "DSA", "SQL", "AI_ML", "BACKEND")


def text_hash(text: str, code: str | None) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", f"{text}|{code or ''}").strip().lower().encode()).hexdigest()


def validate(d: dict, publish: bool) -> None:
    opts = d.get("options") or []
    if len(opts) != 4 or sorted(o.get("id") for o in opts) != ["A", "B", "C", "D"]:
        raise ArenaError("INVALID_QUESTION", "Exactly four options with ids A-D required", 422)
    if any(not str(o.get("text", "")).strip() for o in opts):
        raise ArenaError("INVALID_QUESTION", "Options must be non-empty", 422)
    if len({o["text"].strip() for o in opts}) != 4:
        raise ArenaError("INVALID_QUESTION", "Options must be distinct", 422)
    if d.get("correct_option") not in ("A", "B", "C", "D"):
        raise ArenaError("INVALID_QUESTION", "Exactly one correct option (A-D) required", 422)
    if not str(d.get("question_text", "")).strip():
        raise ArenaError("INVALID_QUESTION", "question_text required", 422)
    if d.get("difficulty") not in DIFFS:
        raise ArenaError("INVALID_QUESTION", f"difficulty must be one of {DIFFS}", 422)
    if publish and not str(d.get("explanation", "")).strip():
        raise ArenaError("INVALID_QUESTION", "Published questions need an explanation", 422)


async def create_question(s: AsyncSession, d: dict, admin_id: str) -> Question:
    if not await s.get(Domain, d["domain_id"]):
        raise ArenaError("INVALID_QUESTION", "Unknown domain_id", 422)
    validate(d, d.get("status") == "PUBLISHED")
    h = text_hash(d["question_text"], d.get("code_snippet"))
    if (await s.execute(select(Question.id).where(Question.text_hash == h))).first():
        raise ArenaError("DUPLICATE_QUESTION", "Question already exists", 409)
    tags = d.pop("tags", [])
    q = Question(**d, text_hash=h, created_by=admin_id)
    s.add(q)
    await s.flush()
    for t in set(tags):
        s.add(QuestionTag(question_id=q.id, tag=t))
    return q


async def update_question(s: AsyncSession, q: Question, d: dict) -> Question:
    merged = {c: getattr(q, c) for c in ("question_text", "options", "correct_option", "explanation", "difficulty",
                                         "code_snippet", "status")} | d
    validate(merged, merged["status"] == "PUBLISHED")
    for k, v in d.items():
        setattr(q, k, v)
    q.text_hash = text_hash(q.question_text, q.code_snippet)
    return q


async def pool_size(s: AsyncSession, domain_id: str) -> int:
    return (await s.execute(select(func.count()).select_from(Question)
                            .where(Question.domain_id == domain_id, Question.status == "PUBLISHED"))).scalar_one()
