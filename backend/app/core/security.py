from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(
    subject: str,
    role: str,
    token_version: int = 0,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "tv": token_version,
        "exp": expires,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc


def utc_now_naive() -> datetime:
    """UTC timestamp without tzinfo for Naive DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)
