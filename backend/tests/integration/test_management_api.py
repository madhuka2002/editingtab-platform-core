import uuid

from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_authorization_service, get_management_service
from app.main import app
from app.models import Organization, User
from app.services import AuthorizationDeniedError, InvalidAuthenticationError


class Authentication:
    def __init__(self, user): self.user = user
    async def get_current_user(self, _token):
        if self.user is None: raise InvalidAuthenticationError()
        return self.user


class Authorization:
    def __init__(self, allowed=True): self.allowed = allowed
    async def require_permission(self, user, organization_id, permission):
        if user.is_super_admin: return None
        if not self.allowed: raise AuthorizationDeniedError()
        return None


class Management:
    def __init__(self, organization, member):
        self.organization_value = organization
        self.member = member

    async def list_organizations(self, limit, offset, active, search): return [self.organization_value], 1
    async def organization(self, organization_id): return self.organization_value
    async def update_organization(self, organization_id, **changes):
        if changes.get("name") is not None: self.organization_value.name = changes["name"]
        if changes.get("is_active") is not None: self.organization_value.is_active = changes["is_active"]
        return self.organization_value
    async def current_organizations(self, user_id):
        return [{"id": self.organization_value.id, "name": self.organization_value.name, "slug": self.organization_value.slug, "is_active": True, "membership_id": uuid.uuid4(), "role_slugs": ["admin"]}]
    async def booking_entitlement(self, organization_id): return True
    async def list_members(self, organization_id): return [self.member]
    async def create_user_membership(self, organization_id, **values): return self.member


def make_user(super_admin=False):
    return User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.com", password_hash="secret-hash", is_active=True, is_super_admin=super_admin)


def setup(user, *, allowed=True):
    organization = Organization(id=uuid.uuid4(), name="Hotel", slug="hotel", is_active=True)
    member = {"membership_id": uuid.uuid4(), "user_id": uuid.uuid4(), "email": "member@example.com", "first_name": None, "last_name": None, "is_active": True, "roles": []}
    management = Management(organization, member)
    app.dependency_overrides[get_auth_service] = lambda: Authentication(user)
    app.dependency_overrides[get_authorization_service] = lambda: Authorization(allowed)
    app.dependency_overrides[get_management_service] = lambda: management
    return organization, management


def teardown(): app.dependency_overrides.clear()


def test_super_admin_can_list_detail_update_and_normal_user_is_blocked():
    organization, _ = setup(make_user(super_admin=True))
    try:
        client = TestClient(app)
        headers = {"Authorization": "Bearer token"}
        assert client.get("/api/v1/organizations", headers=headers).status_code == 200
        assert client.get(f"/api/v1/organizations/{organization.id}", headers=headers).status_code == 200
        response = client.patch(f"/api/v1/organizations/{organization.id}", headers=headers, json={"name": "Renamed", "is_active": False})
        assert response.status_code == 200 and response.json()["is_active"] is False
    finally: teardown()

    setup(make_user(super_admin=False))
    try:
        assert TestClient(app).get("/api/v1/organizations", headers={"Authorization": "Bearer token"}).status_code == 403
    finally: teardown()


def test_me_organizations_uses_memberships_even_for_super_admin():
    organization, _ = setup(make_user(super_admin=True))
    try:
        response = TestClient(app).get("/api/v1/auth/me/organizations", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()[0]["id"] == str(organization.id)
        assert response.json()[0]["role_slugs"] == ["admin"]
    finally: teardown()


def test_entitlement_and_member_responses_are_safe_and_permission_scoped():
    user = make_user()
    organization, _ = setup(user, allowed=True)
    try:
        client = TestClient(app); headers = {"Authorization": "Bearer token"}
        entitlement = client.get(f"/api/v1/organizations/{organization.id}/entitlements/booking", headers=headers)
        members = client.get(f"/api/v1/organizations/{organization.id}/members", headers=headers)
        assert entitlement.json()["is_enabled"] is True
        assert members.status_code == 200
        assert "password_hash" not in str(members.json())
    finally: teardown()

    organization, _ = setup(user, allowed=False)
    try:
        response = TestClient(app).get(f"/api/v1/organizations/{organization.id}/members", headers={"Authorization": "Bearer token"})
        assert response.status_code == 403
    finally: teardown()


def test_create_user_response_never_exposes_password_data():
    organization, _ = setup(make_user(), allowed=True)
    try:
        response = TestClient(app).post(
            f"/api/v1/organizations/{organization.id}/users",
            headers={"Authorization": "Bearer token"},
            json={"email": " NEW@example.com ", "password": "long-password"},
        )
        assert response.status_code == 201
        assert "password" not in str(response.json())
    finally: teardown()
