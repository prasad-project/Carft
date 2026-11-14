from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ArenaError, current_user, make_token
from app.database.models import AdminUser, PlayerStats, User
from app.database.session import get_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class DevLogin(BaseModel):
    username: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str | None = None


@router.post("/dev-login")
async def dev_login(body: DevLogin, s: AsyncSession = Depends(get_session)):
    """Passwordless login for development ONLY (ENABLE_DEV_LOGIN=false in prod; swap in a real IdP)."""
    if not settings.enable_dev_login:
        raise ArenaError("DISABLED", "Dev login disabled", 403)
    u = (await s.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if not u:
        u = User(username=body.username, display_name=body.display_name or body.username)
        s.add(u)
        await s.flush()
        s.add(PlayerStats(user_id=u.id))
        if body.username in [x.strip() for x in settings.admin_usernames.split(",")]:
            s.add(AdminUser(user_id=u.id))
        await s.commit()
    return {"access_token": make_token(u.id), "token_type": "bearer", "user_id": u.id}


@router.get("/me")
async def me(u: User = Depends(current_user)):
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "avatar_url": u.avatar_url}
