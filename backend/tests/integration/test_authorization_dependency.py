import uuid
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_auth_service,
    get_authorization_service,
    require_permission,
)
from app.core.rbac import MEMBERS_READ
from app.models import OrganizationUser, User
from app.services import AuthorizationDeniedError, InvalidAuthenticationError


class AuthenticationStub:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_current_user(self, _token: str) -> User:
        if self.user is None:
            raise InvalidAuthenticationError()
        return self.user


class AuthorizationStub:
    def __init__(self, *, allowed: bool) -> None:
        self.allowed = allowed
        self.calls = 0

    async def require_permission(
        self,
        _user: User,
        _organization_id: uuid.UUID,
        _permission_code: str,
    ) -> None:
        self.calls += 1
        if not self.allowed:
            raise AuthorizationDeniedError()


def make_test_app() -> FastAPI:
    application = FastAPI()

    @application.get("/organizations/{organization_id}/protected")
    async def protected_route(
        _authorization: Annotated[
            OrganizationUser | None,
            Depends(require_permission(MEMBERS_READ)),
        ],
    ) -> dict[str, str]:
        return {"status": "ok"}

    return application


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="rbac-test@example.com",
        password_hash="test-hash",
        is_active=True,
        is_super_admin=False,
    )


def test_unauthenticated_request_fails_before_permission_evaluation() -> None:
    application = make_test_app()
    authorization = AuthorizationStub(allowed=True)
    application.dependency_overrides[get_auth_service] = lambda: (
        AuthenticationStub(None)
    )
    application.dependency_overrides[get_authorization_service] = lambda: (
        authorization
    )

    response = TestClient(application).get(
        f"/organizations/{uuid.uuid4()}/protected",
        headers={"Authorization": "Bearer invalid"},
    )

    assert response.status_code == 401
    assert authorization.calls == 0


def test_authenticated_permission_denial_returns_403() -> None:
    application = make_test_app()
    authorization = AuthorizationStub(allowed=False)
    application.dependency_overrides[get_auth_service] = lambda: (
        AuthenticationStub(make_user())
    )
    application.dependency_overrides[get_authorization_service] = lambda: (
        authorization
    )

    response = TestClient(application).get(
        f"/organizations/{uuid.uuid4()}/protected",
        headers={"Authorization": "Bearer valid"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


def test_authenticated_permitted_request_succeeds() -> None:
    application = make_test_app()
    authorization = AuthorizationStub(allowed=True)
    application.dependency_overrides[get_auth_service] = lambda: (
        AuthenticationStub(make_user())
    )
    application.dependency_overrides[get_authorization_service] = lambda: (
        authorization
    )

    response = TestClient(application).get(
        f"/organizations/{uuid.uuid4()}/protected",
        headers={"Authorization": "Bearer valid"},
    )

    assert response.status_code == 200
    assert authorization.calls == 1
