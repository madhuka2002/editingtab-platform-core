import asyncio
import uuid

import pytest
from sqlalchemy import Boolean
from unittest.mock import AsyncMock, MagicMock

from app.core.rbac import MEMBERS_MANAGE
from app.core.security import verify_password
from app.models import Organization, OrganizationUser, Permission, Role, User
from app.schemas.management import CreateOrganizationUserRequest, RoleCreateRequest
from app.services.management import ManagementConflictError, ManagementNotFoundError, ManagementService


def run(value):
    return asyncio.run(value)


class Uow:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self): self.commits += 1
    async def rollback(self): self.rollbacks += 1


class Repo:
    def __init__(self, organization, membership):
        self.organization = organization
        self.membership = membership
        self.owner_ids = {membership.id}
        self.roles = []
        self.replaced = None
        self.locked = False

    async def find_organization(self, organization_id, *, lock=False):
        self.locked = lock
        return self.organization if organization_id == self.organization.id else None

    async def find_membership(self, organization_id, membership_id):
        return self.membership if organization_id == self.organization.id and membership_id == self.membership.id else None

    async def active_owner_ids(self, organization_id): return self.owner_ids
    async def find_roles(self, organization_id, role_ids): return [role for role in self.roles if role.id in role_ids and role.organization_id == organization_id]
    async def permission_codes_for_roles(self, role_ids): return {MEMBERS_MANAGE} if role_ids else set()
    async def replace_membership_roles(self, organization_id, membership_id, role_ids): self.replaced = role_ids
    async def find_role(self, organization_id, role_id): return next((role for role in self.roles if role.organization_id == organization_id and role.id == role_id), None)
    async def assignment_count(self, organization_id, role_id): return 0
    async def delete_role(self, role): self.roles.remove(role)


def context():
    organization = Organization(id=uuid.uuid4(), name="A", slug="a", is_active=True)
    user = User(id=uuid.uuid4(), email="a@example.com", password_hash="x", is_active=True, is_super_admin=False)
    membership = OrganizationUser(id=uuid.uuid4(), organization_id=organization.id, user_id=user.id, is_active=True)
    repository = Repo(organization, membership)
    uow = Uow()
    return organization, user, membership, repository, uow, ManagementService(repository, uow)


def test_role_active_state_is_non_nullable_boolean_with_default():
    column = Role.__table__.c.is_active
    assert isinstance(column.type, Boolean)
    assert column.nullable is False
    assert column.server_default.arg == "true"


def test_management_inputs_normalize_email_and_reject_blank_role_text():
    request = CreateOrganizationUserRequest(email=" Admin@Example.COM ", password="password1")
    assert str(request.email) == "admin@example.com"
    with pytest.raises(ValueError):
        RoleCreateRequest(name=" ", slug="custom")


def test_final_active_owner_cannot_be_deactivated_and_uses_lock():
    organization, user, membership, repository, uow, service = context()
    with pytest.raises(ManagementConflictError):
        run(service.set_membership_active(organization.id, membership.id, False, uuid.uuid4()))
    assert repository.locked is True
    assert uow.commits == 0 and uow.rollbacks == 1


def test_second_owner_allows_first_owner_deactivation():
    organization, user, membership, repository, uow, service = context()
    repository.owner_ids.add(uuid.uuid4())
    result = run(service.set_membership_active(organization.id, membership.id, False, uuid.uuid4()))
    assert result.is_active is False
    assert uow.commits == 1


def test_self_deactivation_is_blocked():
    organization, user, membership, repository, _, service = context()
    with pytest.raises(ManagementConflictError, match="Self-deactivation"):
        run(service.set_membership_active(organization.id, membership.id, False, user.id))


def test_final_owner_role_cannot_be_removed():
    organization, _, membership, repository, uow, service = context()
    with pytest.raises(ManagementConflictError, match="active owner"):
        run(service.replace_membership_roles(organization.id, membership.id, [], uuid.uuid4()))
    assert repository.replaced is None and uow.rollbacks == 1


def test_caller_cannot_remove_final_members_manage_permission():
    organization, user, membership, repository, _, service = context()
    repository.owner_ids = set()
    with pytest.raises(ManagementConflictError, match="Self-lockout"):
        run(service.replace_membership_roles(organization.id, membership.id, [], user.id))


def test_inactive_and_cross_tenant_roles_cannot_be_assigned():
    organization, _, membership, repository, _, service = context()
    inactive = Role(id=uuid.uuid4(), organization_id=organization.id, name="Custom", slug="custom", is_active=False, is_system=False)
    repository.roles = [inactive]
    with pytest.raises(ManagementConflictError, match="Inactive"):
        run(service.replace_membership_roles(organization.id, membership.id, [inactive.id], uuid.uuid4()))
    with pytest.raises(ManagementNotFoundError):
        run(service.replace_membership_roles(organization.id, membership.id, [uuid.uuid4()], uuid.uuid4()))


def test_system_role_update_and_delete_are_blocked():
    organization, _, _, repository, _, service = context()
    role = Role(id=uuid.uuid4(), organization_id=organization.id, name="Owner", slug="owner", is_system=True, is_active=True)
    repository.roles = [role]
    with pytest.raises(ManagementConflictError, match="System roles"):
        run(service.update_role(organization.id, role.id, name="Changed"))
    with pytest.raises(ManagementConflictError, match="System roles"):
        run(service.delete_role(organization.id, role.id))


def mock_service():
    repository = MagicMock()
    repository.find_organization = AsyncMock()
    repository.find_user_by_email = AsyncMock(return_value=None)
    repository.find_roles = AsyncMock(return_value=[])
    repository.find_membership_for_user = AsyncMock(return_value=None)
    repository.flush = AsyncMock()
    repository.assignment_count = AsyncMock(return_value=0)
    repository.delete_role = AsyncMock()
    repository.find_role = AsyncMock()
    repository.find_permissions = AsyncMock(return_value=[])
    repository.replace_role_permissions = AsyncMock()
    repository.membership_role_ids = AsyncMock(return_value=set())
    repository.permission_codes_for_roles = AsyncMock(return_value=set())
    repository.add = MagicMock()
    repository.add_all = MagicMock()
    uow = Uow()
    return repository, uow, ManagementService(repository, uow)


def test_create_user_and_membership_hashes_password_and_commits_once():
    repository, uow, service = mock_service()
    organization = Organization(id=uuid.uuid4(), name="A", slug="a", is_active=True)
    repository.find_organization.return_value = organization

    result = run(service.create_user_membership(
        organization.id,
        email="new@example.com",
        password="long-password",
        first_name="New",
        last_name=None,
        role_ids=[],
    ))

    user, membership = repository.add_all.call_args_list[0].args[0]
    assert user.password_hash != "long-password"
    assert verify_password("long-password", user.password_hash)
    assert membership.organization_id == organization.id
    assert "password" not in result
    assert uow.commits == 1


def test_attach_rejects_inactive_user_without_writes():
    repository, uow, service = mock_service()
    organization = Organization(id=uuid.uuid4(), name="A", slug="a", is_active=True)
    repository.find_organization.return_value = organization
    repository.find_user_by_email.return_value = User(
        id=uuid.uuid4(), email="inactive@example.com", password_hash="x",
        is_active=False, is_super_admin=False,
    )
    with pytest.raises(ManagementConflictError, match="inactive"):
        run(service.attach_membership(organization.id, email="inactive@example.com", role_ids=[]))
    repository.add.assert_not_called()
    assert uow.rollbacks == 1


def test_custom_role_must_be_inactive_and_unassigned_before_delete():
    repository, uow, service = mock_service()
    organization_id = uuid.uuid4()
    role = Role(id=uuid.uuid4(), organization_id=organization_id, name="Custom", slug="custom", is_system=False, is_active=True)
    repository.find_role.return_value = role
    with pytest.raises(ManagementConflictError, match="inactive and unassigned"):
        run(service.delete_role(organization_id, role.id))
    role.is_active = False
    repository.assignment_count.return_value = 1
    with pytest.raises(ManagementConflictError, match="inactive and unassigned"):
        run(service.delete_role(organization_id, role.id))
    repository.assignment_count.return_value = 0
    run(service.delete_role(organization_id, role.id))
    repository.delete_role.assert_awaited_once_with(role)
    assert uow.commits == 1


def test_system_permissions_cannot_be_replaced():
    repository, _, service = mock_service()
    organization = Organization(id=uuid.uuid4(), name="A", slug="a", is_active=True)
    role = Role(id=uuid.uuid4(), organization_id=organization.id, name="Owner", slug="owner", is_system=True, is_active=True)
    repository.find_organization.return_value = organization
    repository.find_role.return_value = role
    with pytest.raises(ManagementConflictError, match="System role permissions"):
        run(service.replace_role_permissions(organization.id, role.id, [], uuid.uuid4()))


def test_custom_permission_replacement_rejects_unknown_permission():
    repository, _, service = mock_service()
    organization = Organization(id=uuid.uuid4(), name="A", slug="a", is_active=True)
    role = Role(id=uuid.uuid4(), organization_id=organization.id, name="Custom", slug="custom", is_system=False, is_active=True)
    repository.find_organization.return_value = organization
    repository.find_role.return_value = role
    with pytest.raises(ManagementConflictError, match="Unsupported permission"):
        run(service.replace_role_permissions(organization.id, role.id, [uuid.uuid4()], uuid.uuid4()))


def test_custom_permission_replacement_is_atomic():
    repository, uow, service = mock_service()
    organization = Organization(id=uuid.uuid4(), name="A", slug="a", is_active=True)
    role = Role(id=uuid.uuid4(), organization_id=organization.id, name="Custom", slug="custom", is_system=False, is_active=True)
    permission = Permission(id=uuid.uuid4(), code="organization.read")
    repository.find_organization.return_value = organization
    repository.find_role.return_value = role
    repository.find_permissions.return_value = [permission]
    result = run(service.replace_role_permissions(organization.id, role.id, [permission.id], uuid.uuid4()))
    assert result == [permission]
    repository.replace_role_permissions.assert_awaited_once_with(role.id, {permission.id})
    assert uow.commits == 1
