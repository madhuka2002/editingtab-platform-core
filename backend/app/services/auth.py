import uuid
from datetime import UTC, datetime, timedelta

from anyio import to_thread

from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    digest_token,
    hash_password,
    password_hash_needs_upgrade,
    verify_password,
)
from app.models import RefreshToken, User
from app.repositories import RefreshTokenRepository, UserRepository


AUTHENTICATION_ERROR_MESSAGE = "Invalid authentication credentials"
_DUMMY_PASSWORD_HASH = hash_password("authentication-timing-placeholder")


class InvalidAuthenticationError(Exception):
    pass


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        secret_key: str,
        access_token_lifetime: timedelta,
        refresh_token_lifetime: timedelta,
    ) -> None:
        self._users = user_repository
        self._refresh_tokens = refresh_token_repository
        self._secret_key = secret_key
        self._access_token_lifetime = access_token_lifetime
        self._refresh_token_lifetime = refresh_token_lifetime

    async def login(self, email: str, password: str) -> tuple[str, str, int]:
        user = await self._users.find_by_email(email.strip().lower())
        password_is_valid = await to_thread.run_sync(
            verify_password,
            password,
            user.password_hash if user is not None else _DUMMY_PASSWORD_HASH,
        )

        if user is None or not password_is_valid or not user.is_active:
            raise InvalidAuthenticationError(AUTHENTICATION_ERROR_MESSAGE)

        if password_hash_needs_upgrade(user.password_hash):
            user.password_hash = await to_thread.run_sync(hash_password, password)

        return await self._issue_token_pair(user)

    async def refresh(self, token: str) -> tuple[str, str, int]:
        """Rotate a one-time refresh token and issue a new token pair.

        The old persisted digest is revoked in the same transaction that stores
        the replacement digest. Reuse of the old token is rejected.
        """
        claims = self._decode(token, REFRESH_TOKEN_TYPE)
        stored_token = await self._refresh_tokens.find_by_digest_for_update(
            digest_token(token)
        )
        now = datetime.now(UTC)

        if (
            stored_token is None
            or stored_token.id != claims.token_id
            or stored_token.user_id != claims.subject
            or stored_token.revoked_at is not None
            or stored_token.expires_at <= now
        ):
            raise InvalidAuthenticationError(AUTHENTICATION_ERROR_MESSAGE)

        user = await self._users.find_by_id(claims.subject)
        if user is None or not user.is_active:
            raise InvalidAuthenticationError(AUTHENTICATION_ERROR_MESSAGE)

        self._refresh_tokens.revoke(stored_token, now)
        return await self._issue_token_pair(user)

    async def logout(self, token: str) -> None:
        claims = self._decode(token, REFRESH_TOKEN_TYPE, verify_expiration=False)
        stored_token = await self._refresh_tokens.find_by_digest_for_update(
            digest_token(token)
        )

        if stored_token is None:
            return
        if (
            stored_token.id != claims.token_id
            or stored_token.user_id != claims.subject
        ):
            raise InvalidAuthenticationError(AUTHENTICATION_ERROR_MESSAGE)

        self._refresh_tokens.revoke(stored_token, datetime.now(UTC))
        await self._refresh_tokens.commit()

    async def get_current_user(self, access_token: str) -> User:
        claims = self._decode(access_token, ACCESS_TOKEN_TYPE)
        user = await self._users.find_by_id(claims.subject)
        if user is None or not user.is_active:
            raise InvalidAuthenticationError(AUTHENTICATION_ERROR_MESSAGE)
        return user

    async def _issue_token_pair(self, user: User) -> tuple[str, str, int]:
        access_token, _ = create_access_token(
            user.id,
            self._secret_key,
            self._access_token_lifetime,
        )
        refresh_token, token_id, refresh_expires_at = create_refresh_token(
            user.id,
            self._secret_key,
            self._refresh_token_lifetime,
        )
        self._refresh_tokens.add(
            RefreshToken(
                id=token_id,
                user_id=user.id,
                token_digest=digest_token(refresh_token),
                expires_at=refresh_expires_at,
            )
        )
        await self._refresh_tokens.commit()
        return (
            access_token,
            refresh_token,
            int(self._access_token_lifetime.total_seconds()),
        )

    def _decode(
        self,
        token: str,
        expected_type: str,
        *,
        verify_expiration: bool = True,
    ):
        try:
            return decode_token(
                token,
                expected_type,
                self._secret_key,
                verify_expiration=verify_expiration,
            )
        except TokenValidationError as exc:
            raise InvalidAuthenticationError(
                AUTHENTICATION_ERROR_MESSAGE
            ) from exc
