"""Owner tokens (file ownership without a user database) and an in-memory rate limiter.

Each upload returns a random owner token; only its SHA-256 hash is stored. Every later request must
present it (header X-Owner-Token, or ?token= for browser downloads). Wrong token => 404, so resume
ids cannot be probed.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import get_settings


def new_owner_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(token, token_hash: str) -> bool:
    if not token:
        return False
    return hmac.compare_digest(hash_token(token), token_hash)


class RateLimiter:
    """Sliding-window limiter per client IP. Single-process only; use a gateway/Redis for multi-worker."""

    def __init__(self) -> None:
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


async def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(ip, get_settings().rate_limit_per_minute):
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "Too many requests."})
