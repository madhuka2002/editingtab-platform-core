import uuid

from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_provisioning_service
from app.main import app
from app.models import Organization, User
from app.services import InvalidAuthenticationError, ProvisioningError


class AuthenticationStub:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_current_user(self, _token: str) -> User:
        if self.user is None:
            raise InvalidAuthenticationError()
        return self.user


class ProvisioningStub:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def provision(self, name: str, owner_user_id: uuid.UUID):
        self.calls += 1
        if self.fail:
            raise ProvisioningError()
        return Organization(
            id=uuid.uuid4(),
            name=name,
            slug="example-hotel-12345678",
            is_active=True,
        )


def make_user(*, super_admin: bool) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        is_active=True,
        is_super_admin=super_admin,
    )


def request_with(
    authentication: AuthenticationStub,
    provisioning: ProvisioningStub,
):
    app.dependency_overrides[get_auth_service] = lambda: authentication
    app.dependency_overrides[get_provisioning_service] = lambda: provisioning
    try:
        return TestClient(app).post(
            "/api/v1/organizations",
            headers={"Authorization": "Bearer test-token"},
            json={
                "name": "Example Hotel",
                "owner_user_id": str(uuid.uuid4()),
            },
        )
    finally:
        app.dependency_overrides.clear()


def test_unauthenticated_provisioning_returns_401() -> None:
    provisioning = ProvisioningStub()

    response = request_with(AuthenticationStub(None), provisioning)

    assert response.status_code == 401
    assert provisioning.calls == 0


def test_non_super_admin_provisioning_returns_403() -> None:
    provisioning = ProvisioningStub()

    response = request_with(
        AuthenticationStub(make_user(super_admin=False)),
        provisioning,
    )

    assert response.status_code == 403
    assert provisioning.calls == 0


def test_super_admin_can_provision_without_sensitive_response_data() -> None:
    response = request_with(
        AuthenticationStub(make_user(super_admin=True)),
        ProvisioningStub(),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Example Hotel"
    assert "password_hash" not in response.json()
    assert "secret" not in response.json()


def test_invalid_owner_returns_safe_failure() -> None:
    response = request_with(
        AuthenticationStub(make_user(super_admin=True)),
        ProvisioningStub(fail=True),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to provision organization"}
