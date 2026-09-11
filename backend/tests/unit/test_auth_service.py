import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import digest_token, hash_password
from app.models import RefreshToken, User
from app.services.auth import (
    AUTHENTICATION_ERROR_MESSAGE,
    AuthService,
    InvalidAuthenticationError,
)


SECRET_KEY = "unit-test-secret-that-is-not-used-outside-tests"
PASSWORD = "correct horse battery staple"
PASSWORD_HASH = hash_password(PASSWORD)


class InMemoryUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}

    async def find_by_email(self, email: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.email == email),
            None,
        )

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)


class InMemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[str, RefreshToken] = {}
        self.commits = 0

    def add(self, refresh_token: RefreshToken) -> None:
        self.tokens[refresh_token.token_digest] = refresh_token

    async def find_by_digest_for_update(
        self,
        token_digest: str,
    ) -> RefreshToken | None:
        return self.tokens.get(token_digest)

    def revoke(self, refresh_token: RefreshToken, revoked_at: datetime) -> None:
        if refresh_token.revoked_at is None:
            refresh_token.revoked_at = revoked_at

    async def commit(self) -> None:
        self.commits += 1


def make_user(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        password_hash=PASSWORD_HASH,
        first_name="Test",
        last_name="User",
        is_active=active,
        is_super_admin=False,
    )


def make_service(
    user: User,
) -> tuple[AuthService, InMemoryRefreshTokenRepository]:
    token_repository = InMemoryRefreshTokenRepository()
    service = AuthService(
        InMemoryUserRepository([user]),
        token_repository,
        SECRET_KEY,
        timedelta(minutes=5),
        timedelta(days=1),
    )
    return service, token_repository


def run(coroutine):
    return asyncio.run(coroutine)


def assert_generic_authentication_failure(coroutine) -> None:
    with pytest.raises(InvalidAuthenticationError) as error:
        run(coroutine)
    assert str(error.value) == AUTHENTICATION_ERROR_MESSAGE


def test_valid_credentials_persist_only_refresh_token_digest() -> None:
    service, tokens = make_service(make_user())

    access_token, refresh_token, expires_in = run(
        service.login(" USER@EXAMPLE.COM ", PASSWORD)
    )

    assert access_token
    assert refresh_token
    assert expires_in == 300
    assert refresh_token not in tokens.tokens
    assert digest_token(refresh_token) in tokens.tokens
    assert all(
        record.token_digest != refresh_token
        for record in tokens.tokens.values()
    )


def test_invalid_password_and_unknown_email_fail_generically() -> None:
    service, _ = make_service(make_user())

    assert_generic_authentication_failure(
        service.login("user@example.com", "wrong password")
    )
    assert_generic_authentication_failure(
        service.login("unknown@example.com", "wrong password")
    )


def test_inactive_user_cannot_authenticate() -> None:
    service, _ = make_service(make_user(active=False))

    assert_generic_authentication_failure(
        service.login("user@example.com", PASSWORD)
    )


def test_refresh_rotates_token_and_rejects_reuse() -> None:
    service, tokens = make_service(make_user())
    _, original_token, _ = run(service.login("user@example.com", PASSWORD))
    original_record = tokens.tokens[digest_token(original_token)]

    new_access_token, new_refresh_token, _ = run(
        service.refresh(original_token)
    )

    assert new_access_token
    assert new_refresh_token != original_token
    assert original_record.revoked_at is not None
    assert digest_token(new_refresh_token) in tokens.tokens
    assert_generic_authentication_failure(service.refresh(original_token))


def test_revoked_refresh_token_fails() -> None:
    service, tokens = make_service(make_user())
    _, refresh_token, _ = run(service.login("user@example.com", PASSWORD))
    tokens.tokens[digest_token(refresh_token)].revoked_at = datetime.now(UTC)

    assert_generic_authentication_failure(service.refresh(refresh_token))


def test_expired_refresh_token_fails() -> None:
    service, tokens = make_service(make_user())
    _, refresh_token, _ = run(service.login("user@example.com", PASSWORD))
    tokens.tokens[digest_token(refresh_token)].expires_at = (
        datetime.now(UTC) - timedelta(seconds=1)
    )

    assert_generic_authentication_failure(service.refresh(refresh_token))


def test_logout_revokes_refresh_token_and_is_repeat_safe() -> None:
    service, tokens = make_service(make_user())
    _, refresh_token, _ = run(service.login("user@example.com", PASSWORD))

    run(service.logout(refresh_token))
    first_revoked_at = tokens.tokens[digest_token(refresh_token)].revoked_at
    run(service.logout(refresh_token))

    assert first_revoked_at is not None
    assert tokens.tokens[digest_token(refresh_token)].revoked_at == first_revoked_at


def test_inactive_user_is_rejected_for_current_access_token() -> None:
    user = make_user()
    service, _ = make_service(user)
    access_token, _, _ = run(service.login("user@example.com", PASSWORD))
    user.is_active = False

    assert_generic_authentication_failure(
        service.get_current_user(access_token)
    )
