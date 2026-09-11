import asyncio
import uuid

import pytest

from app.core.rbac import (
    CORE_PERMISSION_CODES,
    ORGANIZATION_MANAGE,
    ORGANIZATION_READ,
    PREDEFINED_ROLE_PERMISSIONS,
)
from app.models import OrganizationUser, OrganizationUserRole, Role, User
from app.services.authorization import (
    AUTHORIZATION_ERROR_MESSAGE,
    AuthorizationDeniedError,
    AuthorizationService,
)


class InMemoryAuthorizationRepository:
    def __init__(self) -> None:
        self.memberships: dict[tuple[uuid.UUID, uuid.UUID], OrganizationUser] = {}
        self.roles: dict[uuid.UUID, Role] = {}
        self.permissions: dict[uuid.UUID, frozenset[str]] = {}
        self.slugs: dict[uuid.UUID, frozenset[str]] = {}
        self.assignments: list[OrganizationUserRole] = []
        self.permission_queries = 0

    async def find_membership(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> OrganizationUser | None:
        return self.memberships.get((organization_id, user_id))

    async def find_membership_by_id(
        self,
        membership_id: uuid.UUID,
    ) -> OrganizationUser | None:
        return next(
            (
                membership
                for membership in self.memberships.values()
                if membership.id == membership_id
            ),
            None,
        )

    async def find_role_by_id(self, role_id: uuid.UUID) -> Role | None:
        return self.roles.get(role_id)

    async def find_permission_codes(
        self,
        membership_id: uuid.UUID,
    ) -> frozenset[str]:
        self.permission_queries += 1
        return self.permissions.get(membership_id, frozenset())

    async def find_role_slugs(
        self,
        membership_id: uuid.UUID,
    ) -> frozenset[str]:
        return self.slugs.get(membership_id, frozenset())

    def add_role_assignment(self, assignment: OrganizationUserRole) -> None:
        self.assignments.append(assignment)

    async def commit(self) -> None:
        return None


def run(coroutine):
    return asyncio.run(coroutine)


def make_user(*, super_admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        is_active=True,
        is_super_admin=super_admin,
    )


def add_membership(
    repository: InMemoryAuthorizationRepository,
    user: User,
    organization_id: uuid.UUID,
    *,
    active: bool = True,
) -> OrganizationUser:
    membership = OrganizationUser(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user.id,
        is_active=active,
    )
    repository.memberships[(organization_id, user.id)] = membership
    return membership


def assert_denied(coroutine) -> None:
    with pytest.raises(AuthorizationDeniedError) as error:
        run(coroutine)
    assert str(error.value) == AUTHORIZATION_ERROR_MESSAGE


@pytest.mark.parametrize("role_slug", ["owner", "admin", "staff"])
def test_predefined_roles_receive_expected_permissions(role_slug: str) -> None:
    repository = InMemoryAuthorizationRepository()
    service = AuthorizationService(repository)
    user = make_user()
    organization_id = uuid.uuid4()
    membership = add_membership(repository, user, organization_id)
    repository.slugs[membership.id] = frozenset({role_slug})
    repository.permissions[membership.id] = PREDEFINED_ROLE_PERMISSIONS[role_slug]

    assert run(service.role_slugs(user, organization_id)) == {role_slug}
    assert run(service.effective_permissions(user, organization_id)) == (
        PREDEFINED_ROLE_PERMISSIONS[role_slug]
    )

    if role_slug in {"owner", "admin"}:
        assert PREDEFINED_ROLE_PERMISSIONS[role_slug] == CORE_PERMISSION_CODES
    else:
        assert PREDEFINED_ROLE_PERMISSIONS[role_slug] == {ORGANIZATION_READ}


def test_user_without_membership_and_inactive_membership_are_rejected() -> None:
    repository = InMemoryAuthorizationRepository()
    service = AuthorizationService(repository)
    user = make_user()
    organization_id = uuid.uuid4()

    assert_denied(
        service.require_permission(user, organization_id, ORGANIZATION_READ)
    )
    add_membership(repository, user, organization_id, active=False)
    assert_denied(
        service.require_permission(user, organization_id, ORGANIZATION_READ)
    )


def test_missing_permission_and_cross_organization_access_are_rejected() -> None:
    repository = InMemoryAuthorizationRepository()
    service = AuthorizationService(repository)
    user = make_user()
    organization_a = uuid.uuid4()
    organization_b = uuid.uuid4()
    membership = add_membership(repository, user, organization_a)
    repository.permissions[membership.id] = frozenset({ORGANIZATION_READ})

    assert_denied(
        service.require_permission(user, organization_a, ORGANIZATION_MANAGE)
    )
    assert_denied(
        service.require_permission(user, organization_b, ORGANIZATION_READ)
    )


def test_cross_organization_role_assignment_is_rejected() -> None:
    repository = InMemoryAuthorizationRepository()
    service = AuthorizationService(repository)
    user = make_user()
    organization_a = uuid.uuid4()
    organization_b = uuid.uuid4()
    membership = add_membership(repository, user, organization_a)
    role = Role(
        id=uuid.uuid4(),
        organization_id=organization_b,
        name="Staff",
        slug="staff",
        is_system=True,
    )
    repository.roles[role.id] = role

    assert_denied(service.assign_role(organization_a, membership.id, role.id))
    assert repository.assignments == []


def test_same_organization_role_assignment_succeeds() -> None:
    repository = InMemoryAuthorizationRepository()
    service = AuthorizationService(repository)
    user = make_user()
    organization_id = uuid.uuid4()
    membership = add_membership(repository, user, organization_id)
    role = Role(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name="Staff",
        slug="staff",
        is_system=True,
    )
    repository.roles[role.id] = role

    assignment = run(
        service.assign_role(organization_id, membership.id, role.id)
    )

    assert assignment.organization_id == organization_id
    assert repository.assignments == [assignment]


def test_super_admin_bypasses_membership_and_permission_queries() -> None:
    repository = InMemoryAuthorizationRepository()
    service = AuthorizationService(repository)

    result = run(
        service.require_permission(
            make_user(super_admin=True),
            uuid.uuid4(),
            ORGANIZATION_MANAGE,
        )
    )

    assert result is None
    assert repository.permission_queries == 0
