import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


SECRET_KEY = "unit-test-secret-that-is-not-used-outside-tests"


def test_password_hashing_and_verification() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("incorrect password", password_hash) is False


def test_valid_access_token_decodes() -> None:
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id, SECRET_KEY, timedelta(minutes=5))

    claims = decode_token(token, ACCESS_TOKEN_TYPE, SECRET_KEY)

    assert claims.subject == user_id
    assert claims.token_type == ACCESS_TOKEN_TYPE


def test_expired_and_invalid_access_tokens_are_rejected() -> None:
    token, _ = create_access_token(
        uuid.uuid4(),
        SECRET_KEY,
        timedelta(minutes=1),
        now=datetime.now(UTC) - timedelta(minutes=2),
    )

    with pytest.raises(TokenValidationError):
        decode_token(token, ACCESS_TOKEN_TYPE, SECRET_KEY)
    with pytest.raises(TokenValidationError):
        decode_token("not-a-token", ACCESS_TOKEN_TYPE, SECRET_KEY)
    valid_token, _ = create_access_token(
        uuid.uuid4(),
        "different-signing-secret-that-is-long-enough",
        timedelta(minutes=5),
    )
    with pytest.raises(TokenValidationError):
        decode_token(valid_token, ACCESS_TOKEN_TYPE, SECRET_KEY)


def test_access_and_refresh_token_types_cannot_be_confused() -> None:
    user_id = uuid.uuid4()
    access_token, _ = create_access_token(
        user_id,
        SECRET_KEY,
        timedelta(minutes=5),
    )
    refresh_token, _, _ = create_refresh_token(
        user_id,
        SECRET_KEY,
        timedelta(days=1),
    )

    with pytest.raises(TokenValidationError):
        decode_token(access_token, REFRESH_TOKEN_TYPE, SECRET_KEY)
    with pytest.raises(TokenValidationError):
        decode_token(refresh_token, ACCESS_TOKEN_TYPE, SECRET_KEY)
