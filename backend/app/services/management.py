import uuid

from sqlalchemy.exc import IntegrityError

from app.core.rbac import MEMBERS_MANAGE
from app.core.security import hash_password
from app.models import OrganizationUser, OrganizationUserRole, Role, User
from app.repositories import ManagementRepository, UnitOfWork


class ManagementNotFoundError(Exception):
    pass


class ManagementConflictError(Exception):
    pass


class ManagementService:
    def __init__(self, repository: ManagementRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def list_organizations(self, limit: int, offset: int, active: bool | None, search: str | None):
        return await self._repository.list_organizations(limit, offset, active, search)

    async def organization(self, organization_id: uuid.UUID):
        organization = await self._repository.find_organization(organization_id)
        if organization is None:
            raise ManagementNotFoundError("Organization not found")
        return organization

    async def update_organization(self, organization_id: uuid.UUID, *, name: str | None, is_active: bool | None):
        try:
            organization = await self._repository.find_organization(
                organization_id,
                lock=is_active is True,
            )
            if organization is None:
                raise ManagementNotFoundError("Organization not found")
            if is_active is True and not organization.is_active:
                if not await self._repository.active_owner_ids(organization_id):
                    raise ManagementConflictError(
                        "Organization must retain an active owner"
                    )
            if name is not None:
                organization.name = name
            if is_active is not None:
                organization.is_active = is_active
            await self._unit_of_work.commit()
            return organization
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def current_organizations(self, user_id: uuid.UUID) -> list[dict]:
        rows = await self._repository.current_user_organizations(user_id)
        role_map = await self._repository.role_slugs_for_memberships(
            [membership.id for _, membership in rows]
        )
        result = []
        for organization, membership in rows:
            result.append({
                "id": organization.id,
                "name": organization.name,
                "slug": organization.slug,
                "is_active": organization.is_active,
                "membership_id": membership.id,
                "role_slugs": role_map.get(membership.id, []),
            })
        return result

    async def booking_entitlement(self, organization_id: uuid.UUID) -> bool:
        if await self._repository.find_organization(organization_id) is None:
            raise ManagementNotFoundError("Organization not found")
        entitlement = await self._repository.booking_entitlement(organization_id)
        return entitlement is not None and entitlement.is_enabled

    async def list_members(self, organization_id: uuid.UUID) -> list[dict]:
        await self.organization(organization_id)
        rows = await self._repository.list_members(organization_id)
        role_map = await self._repository.role_map_for_memberships(organization_id, [membership.id for membership, _ in rows])
        return [self._member_dict(membership, user, role_map.get(membership.id, [])) for membership, user in rows]

    async def create_user_membership(self, organization_id: uuid.UUID, *, email: str, password: str, first_name: str | None, last_name: str | None, role_ids: list[uuid.UUID]) -> dict:
        try:
            await self.organization(organization_id)
            if await self._repository.find_user_by_email(email) is not None:
                raise ManagementConflictError("User already exists")
            roles = await self._validated_roles(organization_id, role_ids)
            user = User(id=uuid.uuid4(), email=email, password_hash=hash_password(password), first_name=first_name, last_name=last_name, is_active=True, is_super_admin=False)
            membership = OrganizationUser(id=uuid.uuid4(), organization_id=organization_id, user_id=user.id, is_active=True)
            self._repository.add_all([user, membership])
            await self._repository.flush()
            self._repository.add_all([OrganizationUserRole(organization_id=organization_id, organization_user_id=membership.id, role_id=role.id) for role in roles])
            await self._unit_of_work.commit()
            return self._member_dict(membership, user, roles)
        except IntegrityError as exc:
            await self._unit_of_work.rollback()
            raise ManagementConflictError("User or membership already exists") from exc
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def attach_membership(self, organization_id: uuid.UUID, *, email: str, role_ids: list[uuid.UUID]) -> dict:
        try:
            await self.organization(organization_id)
            user = await self._repository.find_user_by_email(email)
            if user is None:
                raise ManagementNotFoundError("User not found")
            if not user.is_active:
                raise ManagementConflictError("User is inactive")
            if await self._repository.find_membership_for_user(organization_id, user.id) is not None:
                raise ManagementConflictError("Membership already exists")
            roles = await self._validated_roles(organization_id, role_ids)
            membership = OrganizationUser(id=uuid.uuid4(), organization_id=organization_id, user_id=user.id, is_active=True)
            self._repository.add(membership)
            await self._repository.flush()
            self._repository.add_all([OrganizationUserRole(organization_id=organization_id, organization_user_id=membership.id, role_id=role.id) for role in roles])
            await self._unit_of_work.commit()
            return self._member_dict(membership, user, roles)
        except IntegrityError as exc:
            await self._unit_of_work.rollback()
            raise ManagementConflictError("Membership already exists") from exc
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def set_membership_active(self, organization_id: uuid.UUID, membership_id: uuid.UUID, is_active: bool, actor_user_id: uuid.UUID):
        try:
            organization = await self._repository.find_organization(organization_id, lock=True)
            membership = await self._repository.find_membership(organization_id, membership_id)
            if organization is None or membership is None:
                raise ManagementNotFoundError("Membership not found")
            if not is_active and membership.user_id == actor_user_id:
                raise ManagementConflictError("Self-deactivation is not allowed")
            if organization.is_active and not is_active and membership.id in await self._repository.active_owner_ids(organization_id):
                if len(await self._repository.active_owner_ids(organization_id)) <= 1:
                    raise ManagementConflictError("Organization must retain an active owner")
            membership.is_active = is_active
            await self._unit_of_work.commit()
            return membership
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def replace_membership_roles(self, organization_id: uuid.UUID, membership_id: uuid.UUID, role_ids: list[uuid.UUID], actor_user_id: uuid.UUID) -> list[Role]:
        try:
            organization = await self._repository.find_organization(organization_id, lock=True)
            membership = await self._repository.find_membership(organization_id, membership_id)
            if organization is None or membership is None:
                raise ManagementNotFoundError("Membership not found")
            roles = await self._validated_roles(organization_id, role_ids)
            new_ids = {role.id for role in roles}
            owners = await self._repository.active_owner_ids(organization_id)
            owner_ids = {role.id for role in roles if role.is_system and role.slug == "owner"}
            if organization.is_active and membership.is_active and membership.id in owners and not owner_ids and len(owners) <= 1:
                raise ManagementConflictError("Organization must retain an active owner")
            if membership.user_id == actor_user_id:
                permissions = await self._repository.permission_codes_for_roles(new_ids)
                if MEMBERS_MANAGE not in permissions:
                    raise ManagementConflictError("Self-lockout is not allowed")
            await self._repository.replace_membership_roles(organization_id, membership_id, new_ids)
            await self._unit_of_work.commit()
            return roles
        except IntegrityError as exc:
            await self._unit_of_work.rollback()
            raise ManagementConflictError("Role assignment conflict") from exc
        except Exception:
            await self._unit_of_work.rollback()
            raise


    async def list_roles(self, organization_id: uuid.UUID):
        await self.organization(organization_id)
        return await self._repository.list_roles(organization_id)

    async def create_role(self, organization_id: uuid.UUID, *, name: str, slug: str, description: str | None):
        try:
            await self.organization(organization_id)
            role = Role(id=uuid.uuid4(), organization_id=organization_id, name=name.strip(), slug=slug, description=description, is_system=False, is_active=True)
            self._repository.add(role)
            await self._unit_of_work.commit()
            return role
        except IntegrityError as exc:
            await self._unit_of_work.rollback()
            raise ManagementConflictError("Role slug already exists") from exc
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def update_role(self, organization_id: uuid.UUID, role_id: uuid.UUID, **changes):
        try:
            role = await self._repository.find_role(organization_id, role_id)
            if role is None:
                raise ManagementNotFoundError("Role not found")
            if role.is_system:
                raise ManagementConflictError("System roles cannot be modified")
            if (
                changes.get("is_active") is False
                and role.is_active
                and await self._repository.assignment_count(organization_id, role_id)
            ):
                raise ManagementConflictError(
                    "Assigned roles must be unassigned before deactivation"
                )
            for key, value in changes.items():
                if value is not None or key == "description":
                    setattr(role, key, value.strip() if isinstance(value, str) else value)
            await self._unit_of_work.commit()
            return role
        except IntegrityError as exc:
            await self._unit_of_work.rollback()
            raise ManagementConflictError("Role slug already exists") from exc
        except Exception:
            await self._unit_of_work.rollback()
            raise


    async def delete_role(self, organization_id: uuid.UUID, role_id: uuid.UUID) -> None:
        try:
            role = await self._repository.find_role(organization_id, role_id)
            if role is None:
                raise ManagementNotFoundError("Role not found")
            if role.is_system:
                raise ManagementConflictError("System roles cannot be deleted")
            if role.is_active or await self._repository.assignment_count(organization_id, role_id):
                raise ManagementConflictError("Role must be inactive and unassigned")
            await self._repository.delete_role(role)
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def list_permissions(self):
        return await self._repository.list_permissions()

    async def role_permissions(self, organization_id: uuid.UUID, role_id: uuid.UUID):
        if await self._repository.find_role(organization_id, role_id) is None:
            raise ManagementNotFoundError("Role not found")
        return await self._repository.role_permissions(role_id)

    async def replace_role_permissions(
        self,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
        permission_ids: list[uuid.UUID],
        actor_user_id: uuid.UUID,
    ):
        try:
            organization = await self._repository.find_organization(
                organization_id,
                lock=True,
            )
            if organization is None:
                raise ManagementNotFoundError("Organization not found")
            role = await self._repository.find_role(organization_id, role_id)
            if role is None:
                raise ManagementNotFoundError("Role not found")
            if role.is_system:
                raise ManagementConflictError("System role permissions cannot be modified")
            ids = set(permission_ids)
            permissions = await self._repository.find_permissions(ids)
            if len(permissions) != len(ids):
                raise ManagementConflictError("Unsupported permission")
            actor_membership = await self._repository.find_membership_for_user(
                organization_id,
                actor_user_id,
            )
            if actor_membership is not None:
                actor_role_ids = await self._repository.membership_role_ids(
                    organization_id,
                    actor_membership.id,
                )
                if role.id in actor_role_ids:
                    remaining_codes = await self._repository.permission_codes_for_roles(
                        actor_role_ids - {role.id}
                    )
                    replacement_codes = {permission.code for permission in permissions}
                    if MEMBERS_MANAGE not in remaining_codes | replacement_codes:
                        raise ManagementConflictError("Self-lockout is not allowed")
            await self._repository.replace_role_permissions(role.id, ids)
            await self._unit_of_work.commit()
            return permissions
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def _validated_roles(self, organization_id: uuid.UUID, role_ids: list[uuid.UUID]) -> list[Role]:
        ids = set(role_ids)
        roles = await self._repository.find_roles(organization_id, ids)
        if len(roles) != len(ids):
            raise ManagementNotFoundError("Role not found")
        if any(not role.is_active for role in roles):
            raise ManagementConflictError("Inactive roles cannot be assigned")
        return roles

    @staticmethod
    def _member_dict(membership: OrganizationUser, user: User, roles: list[Role]) -> dict:
        return {
            "membership_id": membership.id,
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": membership.is_active,
            "roles": [{"id": role.id, "name": role.name, "slug": role.slug, "is_system": role.is_system, "is_active": role.is_active} for role in roles],
        }
