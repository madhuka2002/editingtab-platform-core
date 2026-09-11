import re
import uuid

from app.core.modules import BOOKING_MODULE
from app.core.rbac import CORE_PERMISSION_CODES, PREDEFINED_ROLE_PERMISSIONS
from app.models import (
    Organization,
    OrganizationUser,
    OrganizationUserRole,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.repositories import ProvisioningRepository, UnitOfWork, UserRepository
from app.services.entitlement import EntitlementService


PROVISIONING_ERROR_MESSAGE = "Unable to provision organization"
_ROLE_NAMES = {"owner": "Owner", "admin": "Admin", "staff": "Staff"}


class ProvisioningError(Exception):
    pass


class OrganizationProvisioningService:
    def __init__(
        self,
        repository: ProvisioningRepository,
        user_repository: UserRepository,
        entitlement_service: EntitlementService,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._users = user_repository
        self._entitlements = entitlement_service
        self._unit_of_work = unit_of_work

    async def provision(
        self,
        name: str,
        owner_user_id: uuid.UUID,
        *,
        enable_booking: bool = True,
    ) -> Organization:
        try:
            normalized_name = name.strip()
            if not normalized_name or len(normalized_name) > 150:
                raise ProvisioningError(PROVISIONING_ERROR_MESSAGE)

            owner = await self._users.find_by_id(owner_user_id)
            if owner is None or not owner.is_active:
                raise ProvisioningError(PROVISIONING_ERROR_MESSAGE)

            organization_id = uuid.uuid4()
            organization = Organization(
                id=organization_id,
                name=normalized_name,
                slug=self._build_slug(normalized_name, organization_id),
                is_active=True,
            )
            self._repository.add_organization(organization)

            owner_membership = OrganizationUser(
                id=uuid.uuid4(),
                organization_id=organization.id,
                user_id=owner.id,
                is_active=True,
            )
            self._repository.add_membership(owner_membership)

            permissions = await self._ensure_permissions()
            roles = await self._ensure_roles(organization.id)
            await self._repository.flush()
            await self._ensure_role_permissions(roles, permissions)
            await self._ensure_owner_assignment(owner_membership, roles["owner"])

            if enable_booking:
                await self._entitlements.ensure_enabled(
                    organization.id,
                    BOOKING_MODULE,
                )

            await self._unit_of_work.commit()
            return organization
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def _ensure_permissions(self) -> dict[str, Permission]:
        permissions = await self._repository.find_permissions(
            CORE_PERMISSION_CODES
        )
        for code in CORE_PERMISSION_CODES - permissions.keys():
            permission = Permission(id=uuid.uuid4(), code=code)
            self._repository.add_permission(permission)
            permissions[code] = permission
        return permissions

    async def _ensure_roles(
        self,
        organization_id: uuid.UUID,
    ) -> dict[str, Role]:
        roles = await self._repository.find_roles(
            organization_id,
            PREDEFINED_ROLE_PERMISSIONS.keys(),
        )
        for slug in PREDEFINED_ROLE_PERMISSIONS.keys() - roles.keys():
            role = Role(
                id=uuid.uuid4(),
                organization_id=organization_id,
                name=_ROLE_NAMES[slug],
                slug=slug,
                is_system=True,
            )
            self._repository.add_role(role)
            roles[slug] = role
        return roles

    async def _ensure_role_permissions(
        self,
        roles: dict[str, Role],
        permissions: dict[str, Permission],
    ) -> None:
        existing = await self._repository.find_role_permission_pairs(
            [role.id for role in roles.values()],
            [permission.id for permission in permissions.values()],
        )
        for slug, permission_codes in PREDEFINED_ROLE_PERMISSIONS.items():
            role = roles[slug]
            for code in permission_codes:
                pair = (role.id, permissions[code].id)
                if pair not in existing:
                    self._repository.add_role_permission(
                        RolePermission(
                            role_id=pair[0],
                            permission_id=pair[1],
                        )
                    )
                    existing.add(pair)

    async def _ensure_owner_assignment(
        self,
        membership: OrganizationUser,
        owner_role: Role,
    ) -> None:
        assignment = await self._repository.find_role_assignment(
            membership.id,
            owner_role.id,
        )
        if assignment is None:
            self._repository.add_role_assignment(
                OrganizationUserRole(
                    organization_id=membership.organization_id,
                    organization_user_id=membership.id,
                    role_id=owner_role.id,
                )
            )

    @staticmethod
    def _build_slug(name: str, organization_id: uuid.UUID) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        base = (base or "organization")[:91].rstrip("-")
        return f"{base}-{organization_id.hex[:8]}"
