import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrganizationModuleEntitlement


class EntitlementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(
        self,
        organization_id: uuid.UUID,
        module_code: str,
    ) -> OrganizationModuleEntitlement | None:
        result = await self._session.execute(
            select(OrganizationModuleEntitlement).where(
                OrganizationModuleEntitlement.organization_id
                == organization_id,
                OrganizationModuleEntitlement.module_code
                == module_code.strip().lower(),
            )
        )
        return result.scalar_one_or_none()

    def add(self, entitlement: OrganizationModuleEntitlement) -> None:
        self._session.add(entitlement)
