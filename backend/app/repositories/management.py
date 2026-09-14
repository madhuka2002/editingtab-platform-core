import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Organization,
    OrganizationModuleEntitlement,
    OrganizationUser,
    OrganizationUserRole,
    Permission,
    Role,
    RolePermission,
    User,
)


class ManagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_organizations(self, limit: int, offset: int, active: bool | None, search: str | None):
        filters = []
        if active is not None:
            filters.append(Organization.is_active == active)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Organization.name.ilike(pattern), Organization.slug.ilike(pattern)))
        total = await self._session.scalar(select(func.count()).select_from(Organization).where(*filters))
        result = await self._session.execute(
            select(Organization).where(*filters).order_by(Organization.name, Organization.id).limit(limit).offset(offset)
        )
        return list(result.scalars()), int(total or 0)

    async def find_organization(self, organization_id: uuid.UUID, *, lock: bool = False) -> Organization | None:
        statement = select(Organization).where(Organization.id == organization_id)
        if lock:
            statement = statement.with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def current_user_organizations(self, user_id: uuid.UUID):
        result = await self._session.execute(
            select(Organization, OrganizationUser)
            .join(OrganizationUser, OrganizationUser.organization_id == Organization.id)
            .where(OrganizationUser.user_id == user_id, OrganizationUser.is_active.is_(True), Organization.is_active.is_(True))
            .order_by(Organization.name, Organization.id)
        )
        return list(result.all())

    async def list_members(self, organization_id: uuid.UUID):
        result = await self._session.execute(
            select(OrganizationUser, User)
            .join(User, User.id == OrganizationUser.user_id)
            .where(OrganizationUser.organization_id == organization_id)
            .order_by(User.email)
        )
        return list(result.all())

    async def role_map_for_memberships(self, organization_id: uuid.UUID, membership_ids: list[uuid.UUID]):
        if not membership_ids:
            return {}
        result = await self._session.execute(
            select(OrganizationUserRole.organization_user_id, Role)
            .join(Role, Role.id == OrganizationUserRole.role_id)
            .where(OrganizationUserRole.organization_id == organization_id, OrganizationUserRole.organization_user_id.in_(membership_ids))
            .order_by(Role.name)
        )
        mapping: dict[uuid.UUID, list[Role]] = {item: [] for item in membership_ids}
        for membership_id, role in result.all():
            mapping[membership_id].append(role)
        return mapping

    async def role_slugs_for_memberships(self, membership_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
        if not membership_ids:
            return {}
        result = await self._session.execute(
            select(OrganizationUserRole.organization_user_id, Role.slug)
            .join(Role, Role.id == OrganizationUserRole.role_id)
            .where(
                OrganizationUserRole.organization_user_id.in_(membership_ids),
                Role.is_active.is_(True),
            )
            .order_by(Role.slug)
        )
        mapping: dict[uuid.UUID, list[str]] = {item: [] for item in membership_ids}
        for membership_id, slug in result.all():
            mapping[membership_id].append(slug)
        return mapping

    async def find_membership(self, organization_id: uuid.UUID, membership_id: uuid.UUID) -> OrganizationUser | None:
        result = await self._session.execute(select(OrganizationUser).where(
            OrganizationUser.organization_id == organization_id,
            OrganizationUser.id == membership_id,
        ))
        return result.scalar_one_or_none()

    async def find_membership_for_user(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationUser | None:
        result = await self._session.execute(select(OrganizationUser).where(
            OrganizationUser.organization_id == organization_id,
            OrganizationUser.user_id == user_id,
        ))
        return result.scalar_one_or_none()

    async def find_user_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email.strip().lower()))
        return result.scalar_one_or_none()

    async def find_roles(self, organization_id: uuid.UUID, role_ids: set[uuid.UUID]) -> list[Role]:
        if not role_ids:
            return []
        result = await self._session.execute(select(Role).where(Role.organization_id == organization_id, Role.id.in_(role_ids)))
        return list(result.scalars())

    async def list_roles(self, organization_id: uuid.UUID) -> list[Role]:
        result = await self._session.execute(select(Role).where(Role.organization_id == organization_id).order_by(Role.name, Role.id))
        return list(result.scalars())

    async def find_role(self, organization_id: uuid.UUID, role_id: uuid.UUID) -> Role | None:
        result = await self._session.execute(select(Role).where(Role.organization_id == organization_id, Role.id == role_id))
        return result.scalar_one_or_none()

    async def assignment_count(self, organization_id: uuid.UUID, role_id: uuid.UUID) -> int:
        value = await self._session.scalar(select(func.count()).select_from(OrganizationUserRole).where(
            OrganizationUserRole.organization_id == organization_id,
            OrganizationUserRole.role_id == role_id,
        ))
        return int(value or 0)

    async def active_owner_ids(self, organization_id: uuid.UUID) -> set[uuid.UUID]:
        result = await self._session.execute(
            select(OrganizationUser.id).join(
                OrganizationUserRole,
                OrganizationUserRole.organization_user_id == OrganizationUser.id,
            ).join(Role, Role.id == OrganizationUserRole.role_id).where(
                OrganizationUser.organization_id == organization_id,
                OrganizationUser.is_active.is_(True),
                Role.organization_id == organization_id,
                Role.slug == "owner",
                Role.is_system.is_(True),
                Role.is_active.is_(True),
            ).distinct()
        )
        return set(result.scalars())

    async def membership_role_ids(self, organization_id: uuid.UUID, membership_id: uuid.UUID) -> set[uuid.UUID]:
        result = await self._session.execute(select(OrganizationUserRole.role_id).where(
            OrganizationUserRole.organization_id == organization_id,
            OrganizationUserRole.organization_user_id == membership_id,
        ))
        return set(result.scalars())

    async def permission_codes_for_roles(self, role_ids: set[uuid.UUID]) -> set[str]:
        if not role_ids:
            return set()
        result = await self._session.execute(select(Permission.code).join(RolePermission).where(RolePermission.role_id.in_(role_ids)).distinct())
        return set(result.scalars())

    async def list_permissions(self) -> list[Permission]:
        return list((await self._session.execute(select(Permission).order_by(Permission.code))).scalars())

    async def role_permissions(self, role_id: uuid.UUID) -> list[Permission]:
        result = await self._session.execute(select(Permission).join(RolePermission).where(RolePermission.role_id == role_id).order_by(Permission.code))
        return list(result.scalars())

    async def find_permissions(self, permission_ids: set[uuid.UUID]) -> list[Permission]:
        if not permission_ids:
            return []
        return list((await self._session.execute(select(Permission).where(Permission.id.in_(permission_ids)))).scalars())

    async def booking_entitlement(self, organization_id: uuid.UUID) -> OrganizationModuleEntitlement | None:
        result = await self._session.execute(select(OrganizationModuleEntitlement).where(
            OrganizationModuleEntitlement.organization_id == organization_id,
            OrganizationModuleEntitlement.module_code == "booking",
        ))
        return result.scalar_one_or_none()

    def add(self, instance: object) -> None:
        self._session.add(instance)

    def add_all(self, instances: list[object]) -> None:
        self._session.add_all(instances)

    async def flush(self) -> None:
        await self._session.flush()

    async def replace_membership_roles(self, organization_id: uuid.UUID, membership_id: uuid.UUID, role_ids: set[uuid.UUID]) -> None:
        await self._session.execute(delete(OrganizationUserRole).where(
            OrganizationUserRole.organization_id == organization_id,
            OrganizationUserRole.organization_user_id == membership_id,
        ))
        self.add_all([OrganizationUserRole(organization_id=organization_id, organization_user_id=membership_id, role_id=role_id) for role_id in role_ids])

    async def replace_role_permissions(self, role_id: uuid.UUID, permission_ids: set[uuid.UUID]) -> None:
        await self._session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        self.add_all([RolePermission(role_id=role_id, permission_id=permission_id) for permission_id in permission_ids])

    async def delete_role(self, role: Role) -> None:
        await self._session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        await self._session.delete(role)
