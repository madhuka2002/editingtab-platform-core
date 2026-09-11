import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

_password_hasher = PasswordHasher()


class TokenValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TokenClaims:
    subject: uuid.UUID
    token_type: str
    issued_at: datetime
    expires_at: datetime
    token_id: uuid.UUID | None = None


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def password_hash_needs_upgrade(password_hash: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_access_token(
    user_id: uuid.UUID,
    secret_key: str,
    lifetime: timedelta,
    *,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + lifetime
    token = jwt.encode(
        {
            "sub": str(user_id),
            "type": ACCESS_TOKEN_TYPE,
            "iat": issued_at,
            "exp": expires_at,
        },
        secret_key,
        algorithm=TOKEN_ALGORITHM,
    )
    return token, expires_at


def create_refresh_token(
    user_id: uuid.UUID,
    secret_key: str,
    lifetime: timedelta,
    *,
    now: datetime | None = None,
) -> tuple[str, uuid.UUID, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + lifetime
    token_id = uuid.uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "type": REFRESH_TOKEN_TYPE,
            "jti": str(token_id),
            "iat": issued_at,
            "exp": expires_at,
        },
        secret_key,
        algorithm=TOKEN_ALGORITHM,
    )
    return token, token_id, expires_at


def decode_token(
    token: str,
    expected_type: str,
    secret_key: str,
    *,
    verify_expiration: bool = True,
) -> TokenClaims:
    required_claims = ["sub", "type", "iat", "exp"]
    if expected_type == REFRESH_TOKEN_TYPE:
        required_claims.append("jti")

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[TOKEN_ALGORITHM],
            options={
                "require": required_claims,
                "verify_exp": verify_expiration,
            },
        )
        if payload["type"] != expected_type:
            raise TokenValidationError("Unexpected token type")

        subject = uuid.UUID(payload["sub"])
        token_id = uuid.UUID(payload["jti"]) if "jti" in payload else None
        issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
        expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("Invalid token") from exc

    return TokenClaims(
        subject=subject,
        token_type=payload["type"],
        issued_at=issued_at,
        expires_at=expires_at,
        token_id=token_id,
    )


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
