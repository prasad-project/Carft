from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ArenaError, current_user
from app.database.models import User
from app.database.session import get_session
from app.game.engine import start_match
from app.services import room_service as rs

router = APIRouter(prefix="/api/v1/rooms", tags=["rooms"])


class RoomIn(BaseModel):
    domain_id: str
    duration_seconds: int = 180
    question_count: int = Field(30, ge=1, le=100)


class JoinIn(BaseModel):
    room_code: str = Field(min_length=4, max_length=8)


class ReadyIn(BaseModel):
    ready: bool = True


@router.post("", status_code=201)
async def create(b: RoomIn, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    return await rs.room_state(s, await rs.create_room(s, u, b.domain_id, b.duration_seconds, b.question_count))


@router.post("/join")
async def join(b: JoinIn, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    return await rs.room_state(s, await rs.join_room(s, u, b.room_code))


@router.get("/{room_id}")
async def get(room_id: str, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    r = await rs.load_room(s, room_id)
    await rs.require_member(s, room_id, u.id)
    return await rs.room_state(s, r)


@router.patch("/{room_id}")
async def settings_(room_id: str, b: RoomIn, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    return await rs.room_state(s, await rs.update_settings(s, u, room_id, b.domain_id, b.duration_seconds,
                                                           b.question_count))


@router.post("/{room_id}/ready")
async def ready(room_id: str, b: ReadyIn = ReadyIn(), s: AsyncSession = Depends(get_session),
                u: User = Depends(current_user)):
    return await rs.room_state(s, await rs.set_ready(s, u, room_id, b.ready))


@router.post("/{room_id}/start")
async def start(room_id: str, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    r = await rs.load_room(s, room_id)
    if r.host_id != u.id:
        raise ArenaError("FORBIDDEN", "Only the host can start the match", 403)
    m = await start_match(s, r)
    return {"match_id": m.id, "room": await rs.room_state(s, r)}


@router.post("/{room_id}/leave")
async def leave(room_id: str, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    return await rs.room_state(s, await rs.leave_room(s, u, room_id))


@router.post("/{room_id}/cancel")
async def cancel(room_id: str, s: AsyncSession = Depends(get_session), u: User = Depends(current_user)):
    return await rs.room_state(s, await rs.cancel_room(s, u, room_id))
