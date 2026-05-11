"""Authentication: JWT bearer + API key.

Two equally valid credentials, in priority order:
  1. ``Authorization: Bearer <jwt>``  — short-lived, issued by /login.
  2. ``X-API-Key: gia_xxx``           — long-lived, programmatic clients.

Either resolves to a User via ``get_current_user`` Depends.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .database import get_db

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Dev convenience — refuse to boot in prod without an explicit secret.
    if os.getenv("ENV", "dev").lower() in {"prod", "production"}:
        raise RuntimeError("JWT_SECRET must be set in production.")
    JWT_SECRET = "dev-insecure-secret-do-not-use-in-prod"  # noqa: S105

JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_TTL_MINUTES", "60"))

API_KEY_PREFIX = "gia_"
API_KEY_BYTES = 32  # 256-bit, base64url ≈ 43 chars

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

bearer_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    # bcrypt has a hard 72-byte limit; truncate defensively.
    return pwd_context.hash(plain[:72])


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain[:72], hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(user_id: str, email: str) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    expires_in = JWT_ACCESS_TOKEN_TTL_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "type": "access",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------
def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, prefix, sha256_hex_hash).

    Raw key is shown to the user once; only the hash is persisted.
    """
    raw = API_KEY_PREFIX + secrets.token_urlsafe(API_KEY_BYTES)
    prefix = raw[: len(API_KEY_PREFIX) + 8]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, prefix, digest


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_api_key(db: Session, raw: str) -> Optional[models.User]:
    if not raw or not raw.startswith(API_KEY_PREFIX):
        return None
    candidate_hash = hash_api_key(raw)
    record = db.query(models.APIKey).filter(models.APIKey.key_hash == candidate_hash).first()
    if not record:
        return None
    if record.revoked_at is not None:
        return None
    if record.expires_at is not None and record.expires_at < datetime.now(timezone.utc):
        return None
    # Constant-time guard against timing attacks (we already matched on hash, but cheap).
    if not hmac.compare_digest(record.key_hash, candidate_hash):
        return None

    record.last_used_at = datetime.now(timezone.utc)
    db.commit()
    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user or not user.is_active:
        return None
    return user


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
_unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    bearer_token: Optional[str] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Resolve the caller from a JWT or API key. Raises 401 if neither is valid."""
    if bearer_token:
        payload = decode_access_token(bearer_token)
        if payload:
            user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
            if user and user.is_active:
                return user

    if api_key:
        user = verify_api_key(db, api_key)
        if user:
            return user

    raise _unauthorized
