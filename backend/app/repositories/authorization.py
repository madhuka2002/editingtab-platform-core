import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OrganizationUser,
    OrganizationUserRole,
    Permission,
    Role,
    RolePermission,
)


class AuthorizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_membership(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> OrganizationUser | None:
        result = await self._session.execute(
            select(OrganizationUser).where(
                OrganizationUser.organization_id == organization_id,
                OrganizationUser.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_membership_by_id(
        self,
        membership_id: uuid.UUID,
    ) -> OrganizationUser | None:
        return await self._session.get(OrganizationUser, membership_id)

    async def find_role_by_id(self, role_id: uuid.UUID) -> Role | None:
        return await self._session.get(Role, role_id)

    async def find_permission_codes(
        self,
        membership_id: uuid.UUID,
    ) -> frozenset[str]:
        result = await self._session.execute(
            select(Permission.code)
            .join(
                RolePermission,
                RolePermission.permission_id == Permission.id,
            )
            .join(
                OrganizationUserRole,
                OrganizationUserRole.role_id == RolePermission.role_id,
            )
            .where(
                OrganizationUserRole.organization_user_id == membership_id
            )
            .distinct()
        )
        return frozenset(result.scalars().all())

    async def find_role_slugs(
        self,
        membership_id: uuid.UUID,
    ) -> frozenset[str]:
        result = await self._session.execute(
            select(Role.slug)
            .join(
                OrganizationUserRole,
                OrganizationUserRole.role_id == Role.id,
            )
            .where(
                OrganizationUserRole.organization_user_id == membership_id
            )
            .distinct()
        )
        return frozenset(result.scalars().all())

    def add_role_assignment(
        self,
        assignment: OrganizationUserRole,
    ) -> None:
        self._session.add(assignment)

    async def commit(self) -> None:
        await self._session.commit()
