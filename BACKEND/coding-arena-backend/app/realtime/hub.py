import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import WebSocket

from app.core.redis import get_redis

CHANNEL = "arena:events"


class Hub:
    """Per-process socket registry. Cross-instance fan-out goes through Redis Pub/Sub."""

    def __init__(self):
        self.rooms: dict[str, dict[str, set[WebSocket]]] = {}

    def add(self, room_id: str, user_id: str, ws: WebSocket):
        self.rooms.setdefault(room_id, {}).setdefault(user_id, set()).add(ws)

    def remove(self, room_id: str, user_id: str, ws: WebSocket) -> bool:
        """Returns True if the user has no sockets left in this process."""
        users = self.rooms.get(room_id, {})
        users.get(user_id, set()).discard(ws)
        if not users.get(user_id):
            users.pop(user_id, None)
            if not users:
                self.rooms.pop(room_id, None)
            return True
        return False

    async def deliver(self, ev: dict):
        to = ev.pop("to", None)
        for uid, socks in list(self.rooms.get(ev["room_id"], {}).items()):
            if to and uid != to:
                continue
            for ws in list(socks):
                try:
                    await ws.send_json(ev)
                except Exception:
                    socks.discard(ws)


hub = Hub()


async def publish(room_id: str, etype: str, payload: dict, to: str | None = None, match_id: str | None = None):
    r = get_redis()
    ev = {"event_id": uuid.uuid4().hex, "room_id": room_id, "match_id": match_id,
          "seq": await r.incr(f"seq:{room_id}"), "ts": datetime.now(timezone.utc).isoformat(),
          "type": etype, "payload": payload, "to": to}
    await r.publish(CHANNEL, json.dumps(ev))


async def start_subscriber() -> asyncio.Task:
    ps = get_redis().pubsub()
    await ps.subscribe(CHANNEL)

    async def loop():
        while True:
            m = await ps.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if m and m.get("type") == "message":
                await hub.deliver(json.loads(m["data"]))
            else:
                await asyncio.sleep(0.005)

    return asyncio.create_task(loop())
