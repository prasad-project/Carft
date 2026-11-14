import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_rules
from app.core.security import ArenaError
from app.database.models import Domain, Room, RoomPlayer, User, now, utc
from app.realtime.hub import publish
from app.services.question_service import pool_size

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
ACTIVE = ("WAITING", "READY")


async def _validate_settings(s: AsyncSession, domain_id: str, duration: int, count: int):
    rules = await get_rules()
    d = await s.get(Domain, domain_id)
    if not d or not d.is_active:
        raise ArenaError("INVALID_SETTINGS", "Unknown or inactive domain", 422)
    if duration not in rules["allowed_durations"]:
        raise ArenaError("INVALID_SETTINGS", f"duration must be one of {rules['allowed_durations']}", 422)
    if not rules["min_questions"] <= count <= rules["max_questions"]:
        raise ArenaError("INVALID_SETTINGS", "question_count out of range", 422)
    need = max(count, settings.min_pool_size)
    have = await pool_size(s, domain_id)
    if have < need:
        raise ArenaError("INSUFFICIENT_QUESTIONS", f"Domain has {have} published questions, needs {need}", 409)


async def load_room(s: AsyncSession, room_id: str) -> Room:
    r = await s.get(Room, room_id)
    if not r:
        raise ArenaError("NOT_FOUND", "Room not found", 404)
    if r.status in ACTIVE and utc(r.expires_at) < now():
        r.status = "EXPIRED"
        await s.commit()
    return r


async def members(s: AsyncSession, room_id: str) -> list[RoomPlayer]:
    return list((await s.execute(select(RoomPlayer).where(RoomPlayer.room_id == room_id)
                                 .order_by(RoomPlayer.joined_at))).scalars())


async def require_member(s: AsyncSession, room_id: str, user_id: str) -> RoomPlayer:
    rp = (await s.execute(select(RoomPlayer).where(RoomPlayer.room_id == room_id,
                                                   RoomPlayer.user_id == user_id))).scalar_one_or_none()
    if not rp:
        raise ArenaError("FORBIDDEN", "Not a member of this room", 403)
    return rp


async def room_state(s: AsyncSession, r: Room) -> dict:
    ps = await members(s, r.id)
    users = {u.id: u for u in (await s.execute(select(User).where(User.id.in_([p.user_id for p in ps])))).scalars()}
    return {"id": r.id, "room_code": r.room_code, "invite_link": f"/join/{r.room_code}", "host_id": r.host_id,
            "domain_id": r.domain_id, "duration_seconds": r.duration_seconds, "question_count": r.question_count,
            "status": r.status, "expires_at": utc(r.expires_at).isoformat(), "max_players": 2,
            "players": [{"user_id": p.user_id, "display_name": users[p.user_id].display_name,
                         "avatar_url": users[p.user_id].avatar_url, "is_ready": p.is_ready,
                         "is_host": p.user_id == r.host_id} for p in ps]}


async def broadcast_state(s: AsyncSession, r: Room, etype: str = "room.state"):
    await publish(r.id, etype, await room_state(s, r))


async def create_room(s: AsyncSession, user: User, domain_id: str, duration: int, count: int) -> Room:
    await _validate_settings(s, domain_id, duration, count)
    for _ in range(10):
        r = Room(room_code="".join(secrets.choice(ALPHABET) for _ in range(6)), host_id=user.id, domain_id=domain_id,
                 duration_seconds=duration, question_count=count,
                 expires_at=now() + timedelta(minutes=settings.room_ttl_minutes))
        s.add(r)
        try:
            await s.flush()
            break
        except IntegrityError:  # code collision
            await s.rollback()
    else:
        raise ArenaError("CONFLICT", "Could not allocate room code", 503)
    s.add(RoomPlayer(room_id=r.id, user_id=user.id, is_ready=True))
    await s.commit()
    return r


async def join_room(s: AsyncSession, user: User, code: str) -> Room:
    r = (await s.execute(select(Room).where(Room.room_code == code.strip().upper()))).scalar_one_or_none()
    if not r:
        raise ArenaError("NOT_FOUND", "Invalid room code", 404)
    r = await load_room(s, r.id)
    if r.status == "EXPIRED":
        raise ArenaError("ROOM_EXPIRED", "Room expired", 410)
    if r.status not in ACTIVE:
        raise ArenaError("ROOM_CLOSED", "Room is not accepting players", 409)
    ps = await members(s, r.id)
    if any(p.user_id == user.id for p in ps):
        return r
    if len(ps) >= 2:
        raise ArenaError("ROOM_FULL", "Room is full", 409)
    s.add(RoomPlayer(room_id=r.id, user_id=user.id, is_ready=False))
    r.status = "WAITING"
    try:
        await s.commit()
    except IntegrityError:
        await s.rollback()
        raise ArenaError("ROOM_FULL", "Room is full", 409)
    await broadcast_state(s, r, "room.player_joined")
    return r


async def set_ready(s: AsyncSession, user: User, room_id: str, ready: bool) -> Room:
    r = await load_room(s, room_id)
    rp = await require_member(s, room_id, user.id)
    if r.status not in ACTIVE:
        raise ArenaError("ROOM_CLOSED", "Room is not in a ready-able state", 409)
    rp.is_ready = ready
    await s.flush()
    ps = await members(s, room_id)
    r.status = "READY" if len(ps) == 2 and all(p.is_ready for p in ps) else "WAITING"
    await s.commit()
    await broadcast_state(s, r, "room.player_ready")
    return r


async def update_settings(s: AsyncSession, user: User, room_id: str, domain_id: str, duration: int, count: int) -> Room:
    r = await load_room(s, room_id)
    if r.host_id != user.id:
        raise ArenaError("FORBIDDEN", "Only the host can change settings", 403)
    if r.status not in ACTIVE:
        raise ArenaError("ROOM_CLOSED", "Settings are locked", 409)
    await _validate_settings(s, domain_id, duration, count)
    r.domain_id, r.duration_seconds, r.question_count = domain_id, duration, count
    for p in await members(s, room_id):  # settings changed -> guests must re-confirm
        p.is_ready = p.user_id == r.host_id
    r.status = "WAITING"
    await s.commit()
    await broadcast_state(s, r)
    return r


async def leave_room(s: AsyncSession, user: User, room_id: str) -> Room:
    r = await load_room(s, room_id)
    rp = await require_member(s, room_id, user.id)
    if r.status not in ACTIVE:
        raise ArenaError("ROOM_CLOSED", "Cannot leave once the match started", 409)
    if user.id == r.host_id:
        return await cancel_room(s, user, room_id)
    await s.execute(delete(RoomPlayer).where(RoomPlayer.id == rp.id))
    r.status = "WAITING"
    await s.commit()
    await broadcast_state(s, r, "room.player_left")
    return r


async def cancel_room(s: AsyncSession, user: User, room_id: str) -> Room:
    r = await load_room(s, room_id)
    if r.host_id != user.id:
        raise ArenaError("FORBIDDEN", "Only the host can cancel", 403)
    if r.status not in ACTIVE:
        raise ArenaError("ROOM_CLOSED", "Room can no longer be cancelled", 409)
    r.status = "CANCELLED"
    await s.commit()
    await publish(r.id, "match.cancelled", {"reason": "HOST_CANCELLED"})
    return r
