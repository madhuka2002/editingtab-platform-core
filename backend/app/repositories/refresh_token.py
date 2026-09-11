from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, refresh_token: RefreshToken) -> None:
        self._session.add(refresh_token)

    async def find_by_digest_for_update(
        self,
        token_digest: str,
    ) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken)
            .where(RefreshToken.token_digest == token_digest)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    def revoke(self, refresh_token: RefreshToken, revoked_at: datetime) -> None:
        if refresh_token.revoked_at is None:
            refresh_token.revoked_at = revoked_at

    async def commit(self) -> None:
        await self._session.commit()
