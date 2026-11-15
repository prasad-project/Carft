import hashlib
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.util import utcnow

bearer = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, role: str = "user", minutes: int = 60) -> str:
    """For tests/dev only. In production your existing auth service issues tokens."""
    s = get_settings()
    return jwt.encode({"sub": str(user_id), "role": role, "exp": utcnow() + timedelta(minutes=minutes)},
                      s.jwt_secret, algorithm=s.jwt_algorithm)


def current_user_optional(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                          db: Session = Depends(get_db)) -> User | None:
    if not creds:
        return None
    s = get_settings()
    try:
        claims = jwt.decode(creds.credentials, s.jwt_secret, algorithms=[s.jwt_algorithm])
        uid = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(401, "Unknown or inactive user")
    return user


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if not user:
        raise HTTPException(401, "Authentication required")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    # Role comes from the DB row, not the token, so revoking admin takes effect immediately.
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def viewer_key(request: Request, user: User | None) -> str:
    if user:
        return f"u:{user.id}"
    raw = f"{request.client.host if request.client else ''}|{request.headers.get('user-agent', '')}"
    return "a:" + hashlib.sha256((get_settings().viewer_hash_secret + raw).encode()).hexdigest()[:40]
