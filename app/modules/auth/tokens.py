from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import settings


class InvalidAccessTokenError(ValueError):
    """An access token is missing, malformed, expired, or invalid."""


def _jwt_secret() -> str:
    secret = settings.auth_jwt_secret
    if secret is None or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("AUTH_JWT_SECRET must be configured with at least 32 bytes")
    return secret


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iss": settings.auth_jwt_issuer,
        "aud": settings.auth_jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=settings.auth_access_token_ttl_seconds),
        "jti": secrets.token_urlsafe(16),
        "typ": "access",
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            issuer=settings.auth_jwt_issuer,
            audience=settings.auth_jwt_audience,
            options={"require": ["sub", "iss", "aud", "iat", "exp", "jti"]},
        )
        if payload.get("typ") != "access":
            raise InvalidAccessTokenError("wrong token type")
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise InvalidAccessTokenError("invalid access token") from error


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
