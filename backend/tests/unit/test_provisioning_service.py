import asyncio
import uuid

import pytest

from app.core.modules import BOOKING_MODULE
from app.core.rbac import CORE_PERMISSION_CODES, PREDEFINED_ROLE_PERMISSIONS
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
from app.services.entitlement import EntitlementService
from app.services.provisioning import (
    OrganizationProvisioningService,
    ProvisioningError,
)


class ProvisioningState:
    def __init__(self) -> None:
        self.organizations: list[Organization] = []
        self.memberships: list[OrganizationUser] = []
        self.permissions: dict[str, Permission] = {}
        self.roles: list[Role] = []
        self.role_permissions: list[RolePermission] = []
        self.assignments: list[OrganizationUserRole] = []
        self.entitlements: dict[
            tuple[uuid.UUID, str],
            OrganizationModuleEntitlement,
        ] = {}


class TransactionStub:
    def __init__(self, state: ProvisioningState) -> None:
        self.state = state
        self.commits = 0
        self.rollbacks = 0
        self._snapshot = self._capture()

    def _capture(self):
        return (
            list(self.state.organizations),
            list(self.state.memberships),
            dict(self.state.permissions),
            list(self.state.roles),
            list(self.state.role_permissions),
            list(self.state.assignments),
            dict(self.state.entitlements),
        )

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1
        (
            self.state.organizations,
            self.state.memberships,
            self.state.permissions,
            self.state.roles,
            self.state.role_permissions,
            self.state.assignments,
            self.state.entitlements,
        ) = self._snapshot


class UserRepositoryStub:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)


class ProvisioningRepositoryStub:
    def __init__(
        self,
        state: ProvisioningState,
        *,
        fail_mapping: bool = False,
    ) -> None:
        self.state = state
        self.fail_mapping = fail_mapping

    def add_organization(self, organization: Organization) -> None:
        self.state.organizations.append(organization)

    def add_membership(self, membership: OrganizationUser) -> None:
        self.state.memberships.append(membership)

    async def find_permissions(self, codes) -> dict[str, Permission]:
        return {
            code: permission
            for code, permission in self.state.permissions.items()
            if code in codes
        }

    def add_permission(self, permission: Permission) -> None:
        self.state.permissions[permission.code] = permission

    async def find_roles(self, organization_id, slugs) -> dict[str, Role]:
        return {
            role.slug: role
            for role in self.state.roles
            if role.organization_id == organization_id and role.slug in slugs
        }

    def add_role(self, role: Role) -> None:
        self.state.roles.append(role)

    async def find_role_permission_pairs(self, role_ids, permission_ids):
        role_ids = set(role_ids)
        permission_ids = set(permission_ids)
        return {
            (mapping.role_id, mapping.permission_id)
            for mapping in self.state.role_permissions
            if mapping.role_id in role_ids
            and mapping.permission_id in permission_ids
        }

    def add_role_permission(self, mapping: RolePermission) -> None:
        if self.fail_mapping:
            raise RuntimeError("injected mapping failure")
        self.state.role_permissions.append(mapping)

    async def find_role_assignment(self, membership_id, role_id):
        return next(
            (
                assignment
                for assignment in self.state.assignments
                if assignment.organization_user_id == membership_id
                and assignment.role_id == role_id
            ),
            None,
        )

    def add_role_assignment(self, assignment: OrganizationUserRole) -> None:
        self.state.assignments.append(assignment)

    async def flush(self) -> None:
        return None


class EntitlementRepositoryStub:
    def __init__(self, state: ProvisioningState) -> None:
        self.state = state

    async def find(self, organization_id, module_code):
        return self.state.entitlements.get((organization_id, module_code))

    def add(self, entitlement: OrganizationModuleEntitlement) -> None:
        self.state.entitlements[
            (entitlement.organization_id, entitlement.module_code)
        ] = entitlement


def run(coroutine):
    return asyncio.run(coroutine)


def make_user(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        is_active=active,
        is_super_admin=False,
    )


def make_service(
    state: ProvisioningState,
    owner: User,
    *,
    fail_mapping: bool = False,
):
    transaction = TransactionStub(state)
    entitlement_service = EntitlementService(
        EntitlementRepositoryStub(state),
        transaction,
    )
    service = OrganizationProvisioningService(
        ProvisioningRepositoryStub(state, fail_mapping=fail_mapping),
        UserRepositoryStub([owner]),
        entitlement_service,
        transaction,
    )
    return service, transaction


def test_provisioning_creates_usable_booking_organization() -> None:
    state = ProvisioningState()
    owner = make_user()
    service, transaction = make_service(state, owner)

    organization = run(service.provision("Example Hotel", owner.id))

    assert state.organizations == [organization]
    membership = state.memberships[0]
    assert membership.organization_id == organization.id
    assert membership.user_id == owner.id
    assert membership.is_active is True

    roles = {
        role.slug: role
        for role in state.roles
        if role.organization_id == organization.id
    }
    assert set(roles) == {"owner", "admin", "staff"}
    assert all(role.is_system for role in roles.values())
    assert set(state.permissions) == CORE_PERMISSION_CODES

    actual_mappings = {
        (mapping.role_id, mapping.permission_id)
        for mapping in state.role_permissions
    }
    expected_mappings = {
        (roles[slug].id, state.permissions[code].id)
        for slug, codes in PREDEFINED_ROLE_PERMISSIONS.items()
        for code in codes
    }
    assert actual_mappings == expected_mappings
    assert len(state.role_permissions) == len(actual_mappings)
    run(service._ensure_role_permissions(roles, state.permissions))
    assert len(state.role_permissions) == len(actual_mappings)
    assert any(
        assignment.organization_user_id == membership.id
        and assignment.role_id == roles["owner"].id
        for assignment in state.assignments
    )
    entitlement = state.entitlements[(organization.id, BOOKING_MODULE)]
    assert entitlement.is_enabled is True
    assert transaction.commits == 1
    assert transaction.rollbacks == 0


def test_existing_permissions_are_reused_across_organizations() -> None:
    state = ProvisioningState()
    state.permissions = {
        code: Permission(id=uuid.uuid4(), code=code)
        for code in CORE_PERMISSION_CODES
    }
    original_permission_ids = {
        code: permission.id for code, permission in state.permissions.items()
    }
    owner_a = make_user()
    owner_b = make_user()

    service_a, _ = make_service(state, owner_a)
    organization_a = run(service_a.provision("Organization A", owner_a.id))
    service_b, _ = make_service(state, owner_b)
    organization_b = run(service_b.provision("Organization B", owner_b.id))

    assert len(state.permissions) == len(CORE_PERMISSION_CODES)
    assert {
        code: permission.id for code, permission in state.permissions.items()
    } == original_permission_ids
    assert {role.organization_id for role in state.roles} == {
        organization_a.id,
        organization_b.id,
    }
    assert len(state.roles) == 6
    assert len(state.role_permissions) == 18
    assert len(
        {(mapping.role_id, mapping.permission_id) for mapping in state.role_permissions}
    ) == 18
    assert set(state.entitlements) == {
        (organization_a.id, BOOKING_MODULE),
        (organization_b.id, BOOKING_MODULE),
    }
    membership_organizations = {
        membership.id: membership.organization_id
        for membership in state.memberships
    }
    role_organizations = {role.id: role.organization_id for role in state.roles}
    assert all(
        membership_organizations[assignment.organization_user_id]
        == role_organizations[assignment.role_id]
        for assignment in state.assignments
    )


def test_provisioning_rolls_back_every_step_on_failure() -> None:
    state = ProvisioningState()
    owner = make_user()
    service, transaction = make_service(state, owner, fail_mapping=True)

    with pytest.raises(RuntimeError, match="injected mapping failure"):
        run(service.provision("Rollback Hotel", owner.id))

    assert state.organizations == []
    assert state.memberships == []
    assert state.permissions == {}
    assert state.roles == []
    assert state.role_permissions == []
    assert state.assignments == []
    assert state.entitlements == {}
    assert transaction.commits == 0
    assert transaction.rollbacks == 1


def test_invalid_or_inactive_owner_is_rejected_safely() -> None:
    state = ProvisioningState()
    inactive_owner = make_user(active=False)
    service, transaction = make_service(state, inactive_owner)

    with pytest.raises(ProvisioningError):
        run(service.provision("Example Hotel", inactive_owner.id))
    with pytest.raises(ProvisioningError):
        run(service.provision("Example Hotel", uuid.uuid4()))

    assert state.organizations == []
    assert transaction.commits == 0
    assert transaction.rollbacks == 2


def test_service_rejects_blank_name_and_limits_generated_slug_length() -> None:
    state = ProvisioningState()
    owner = make_user()
    service, _ = make_service(state, owner)

    with pytest.raises(ProvisioningError):
        run(service.provision("   ", owner.id))

    organization = run(service.provision("A" * 150, owner.id))
    assert len(organization.slug) <= 100
