from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service
from app.main import app
from tests.unit.test_auth_service import PASSWORD, make_service, make_user


def test_login_and_current_user_responses_are_safe() -> None:
    user = make_user()
    service, _ = make_service(user)
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"email": " USER@EXAMPLE.COM ", "password": PASSWORD},
            )
            assert login_response.status_code == 200
            login_body = login_response.json()
            assert "password_hash" not in login_body

            me_response = client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {login_body['access_token']}"
                },
            )
            assert me_response.status_code == 200
            assert me_response.json()["email"] == "user@example.com"
            assert "password_hash" not in me_response.json()
    finally:
        app.dependency_overrides.clear()


def test_current_user_requires_authentication() -> None:
    service, _ = make_service(make_user())
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json() == {
            "detail": "Invalid authentication credentials"
        }
    finally:
        app.dependency_overrides.clear()


def test_refresh_rotates_and_logout_revokes_token() -> None:
    service, _ = make_service(make_user())
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": PASSWORD},
            )
            original_refresh_token = login_response.json()["refresh_token"]

            refresh_response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": original_refresh_token},
            )
            assert refresh_response.status_code == 200
            rotated_refresh_token = refresh_response.json()["refresh_token"]
            assert rotated_refresh_token != original_refresh_token

            reused_response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": original_refresh_token},
            )
            assert reused_response.status_code == 401

            logout_response = client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": rotated_refresh_token},
            )
            assert logout_response.status_code == 204

            revoked_response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": rotated_refresh_token},
            )
            assert revoked_response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_inactive_current_user_is_rejected() -> None:
    user = make_user()
    service, _ = make_service(user)
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": PASSWORD},
            )
            user.is_active = False
            response = client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": (
                        f"Bearer {login_response.json()['access_token']}"
                    )
                },
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
