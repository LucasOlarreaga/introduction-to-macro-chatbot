from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import HTTPException, Header
from typing import Optional
from . import config

_serializer = URLSafeTimedSerializer(config.SECRET_KEY)

TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def create_token(role: str) -> str:
    """Create a signed token for the given role ('user' or 'admin')."""
    return _serializer.dumps(role, salt="gsem-auth")


def verify_token(token: str) -> Optional[str]:
    """Return the role if the token is valid, else None."""
    try:
        return _serializer.loads(token, salt="gsem-auth", max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def require_user(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency — requires a valid user or admin token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    role = verify_token(token)
    if role not in ("user", "admin"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return role


def require_admin(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency — requires an admin token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    role = verify_token(token)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return role
