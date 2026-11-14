import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import ArenaError, user_from_token
from app.database.session import SessionLocal
from app.game import engine
from app.realtime.hub import hub, publish
from app.services import room_service as rs

router = APIRouter()


class AnswerIn(BaseModel):
    question_id: str
    option: str = Field(pattern="^[A-D]$")
    request_id: str = Field(min_length=1, max_length=64)


class ReadyIn(BaseModel):
    ready: bool = True


@router.websocket("/ws/game/{room_id}")
async def game_ws(ws: WebSocket, room_id: str, token: str = ""):
    """Channel is keyed by room_id (lobby + the match started from it). Events carry match_id once a match exists."""
    async with SessionLocal() as s:
        try:
            user = await user_from_token(s, token)
            await rs.require_member(s, room_id, user.id)
        except ArenaError as e:
            await ws.close(code=4401 if e.status == 401 else 4403)
            return
    await ws.accept()
    hub.add(room_id, user.id, ws)
    to = user.id
    try:
        async with SessionLocal() as s:
            r = await rs.load_room(s, room_id)
            await publish(room_id, "room.state", await rs.room_state(s, r), to=to)
        if mid := await engine.match_for_room(room_id):
            await engine.set_presence(mid, user.id, True)
            await publish(room_id, "match.player_reconnected", {"user_id": user.id}, match_id=mid)
            await publish(room_id, "match.state", await engine.snapshot(mid, user.id), to=to, match_id=mid)
        while True:
            msg = await ws.receive_json()
            sec = int(time.time())
            r_ = get_redis()
            if await r_.incr(f"rl:{user.id}:{sec}") > settings.ws_rate_limit_per_sec:
                await r_.expire(f"rl:{user.id}:{sec}", 2)
                await publish(room_id, "match.error", {"code": "RATE_LIMITED", "message": "Slow down"}, to=to)
                continue
            await r_.expire(f"rl:{user.id}:{sec}", 2)
            try:
                await _dispatch(room_id, user, msg)
            except (ArenaError, ValidationError, KeyError, TypeError) as e:
                code, text = (e.code, e.message) if isinstance(e, ArenaError) else ("BAD_PAYLOAD", str(e)[:200])
                await publish(room_id, "match.error", {"code": code, "message": text,
                                                       "request_id": (msg.get("payload") or {}).get("request_id")
                                                       if isinstance(msg, dict) else None}, to=to)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if hub.remove(room_id, user.id, ws):
            if mid := await engine.match_for_room(room_id):
                await engine.set_presence(mid, user.id, False)
                await publish(room_id, "match.player_disconnected",
                              {"user_id": user.id, "reconnect_window_seconds": settings.reconnect_window_seconds},
                              match_id=mid)


async def _dispatch(room_id: str, user, msg: dict):
    t, p = msg.get("type"), msg.get("payload") or {}
    if t == "match.ping":
        await publish(room_id, "match.pong", {"server_now_ms": engine.ms()}, to=user.id)
    elif t == "match.answer":
        a = AnswerIn(**p)
        mid = await engine.match_for_room(room_id)
        if not mid:
            raise ArenaError("MATCH_NOT_ACTIVE", "No active match")
        await engine.submit_answer(mid, user.id, a.question_id, a.option, a.request_id)
    elif t in ("match.reconnect", "room.join"):
        async with SessionLocal() as s:
            await publish(room_id, "room.state", await rs.room_state(s, await rs.load_room(s, room_id)), to=user.id)
        if mid := await engine.match_for_room(room_id):
            await publish(room_id, "match.state", await engine.snapshot(mid, user.id), to=user.id, match_id=mid)
    elif t == "room.ready":
        async with SessionLocal() as s:
            await rs.set_ready(s, user, room_id, ReadyIn(**p).ready)
    elif t == "room.leave":
        async with SessionLocal() as s:
            await rs.leave_room(s, user, room_id)
    elif t == "room.start":
        async with SessionLocal() as s:
            r = await rs.load_room(s, room_id)
            if r.host_id != user.id:
                raise ArenaError("FORBIDDEN", "Only the host can start", 403)
            await engine.start_match(s, r)
    else:
        raise ArenaError("UNKNOWN_EVENT", f"Unknown event {t!r}")
