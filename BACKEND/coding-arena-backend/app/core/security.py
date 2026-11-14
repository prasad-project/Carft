from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models import AdminUser, User
from app.database.session import get_session


class ArenaError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


def make_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_ttl_minutes)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> str:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise ArenaError("UNAUTHORIZED", "Invalid or expired token", 401)


async def user_from_token(session: AsyncSession, token: str) -> User:
    u = await session.get(User, decode_token(token))
    if not u:
        raise ArenaError("UNAUTHORIZED", "Unknown user", 401)
    return u


async def current_user(authorization: str = Header(default=""), session: AsyncSession = Depends(get_session)) -> User:
    if not authorization.startswith("Bearer "):
        raise ArenaError("UNAUTHORIZED", "Missing bearer token", 401)
    return await user_from_token(session, authorization[7:])


async def admin_user(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> User:
    if not (await session.execute(select(AdminUser).where(AdminUser.user_id == user.id))).scalar_one_or_none():
        raise ArenaError("FORBIDDEN", "Admin only", 403)
    return user
