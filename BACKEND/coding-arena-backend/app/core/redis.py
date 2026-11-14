import json

import redis.asyncio as aioredis
from fakeredis import FakeAsyncRedis, FakeServer

from app.core.config import DEFAULT_RULES, settings

_r = None


def init_redis(fresh: bool = False):
    global _r
    if _r is None or fresh:
        _r = (FakeAsyncRedis(server=FakeServer(), decode_responses=True) if settings.redis_url.startswith("fakeredis")
              else aioredis.from_url(settings.redis_url, decode_responses=True))
    return _r


def get_redis():
    return init_redis()


async def get_rules() -> dict:
    raw = await get_redis().hgetall("arena:rules")
    return {**DEFAULT_RULES, **{k: json.loads(v) for k, v in raw.items()}}
