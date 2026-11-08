from uuid import uuid4

import pytest

from app.core.config import settings
from app.modules.auth.tokens import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_refresh_token,
)


def test_access_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_jwt_secret", "x" * 48)
    user_id = uuid4()

    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_tampered_access_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_jwt_secret", "x" * 48)
    token = create_access_token(uuid4())

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token + "tampered")


def test_refresh_token_fingerprint_is_not_raw_token() -> None:
    raw_token = "random-high-entropy-refresh-token"

    fingerprint = hash_refresh_token(raw_token)

    assert fingerprint != raw_token
    assert len(fingerprint) == 64
