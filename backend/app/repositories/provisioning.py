import uuid
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Organization,
    OrganizationUser,
    OrganizationUserRole,
    Permission,
    Role,
    RolePermission,
)


class ProvisioningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_organization(self, organization: Organization) -> None:
        self._session.add(organization)

    def add_membership(self, membership: OrganizationUser) -> None:
        self._session.add(membership)

    async def find_permissions(
        self,
        codes: Collection[str],
    ) -> dict[str, Permission]:
        result = await self._session.execute(
            select(Permission).where(Permission.code.in_(codes))
        )
        return {permission.code: permission for permission in result.scalars()}

    def add_permission(self, permission: Permission) -> None:
        self._session.add(permission)

    async def find_roles(
        self,
        organization_id: uuid.UUID,
        slugs: Collection[str],
    ) -> dict[str, Role]:
        result = await self._session.execute(
            select(Role).where(
                Role.organization_id == organization_id,
                Role.slug.in_(slugs),
            )
        )
        return {role.slug: role for role in result.scalars()}

    def add_role(self, role: Role) -> None:
        self._session.add(role)

    async def find_role_permission_pairs(
        self,
        role_ids: Collection[uuid.UUID],
        permission_ids: Collection[uuid.UUID],
    ) -> set[tuple[uuid.UUID, uuid.UUID]]:
        result = await self._session.execute(
            select(RolePermission.role_id, RolePermission.permission_id).where(
                RolePermission.role_id.in_(role_ids),
                RolePermission.permission_id.in_(permission_ids),
            )
        )
        return set(result.tuples())

    def add_role_permission(self, mapping: RolePermission) -> None:
        self._session.add(mapping)

    async def find_role_assignment(
        self,
        membership_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> OrganizationUserRole | None:
        return await self._session.get(
            OrganizationUserRole,
            (membership_id, role_id),
        )

    def add_role_assignment(self, assignment: OrganizationUserRole) -> None:
        self._session.add(assignment)

    async def flush(self) -> None:
        await self._session.flush()
