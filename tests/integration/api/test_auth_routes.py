import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import PasswordHasher
from app.main import create_app
from app.models.auth_refresh_token import RefreshTokenStatus
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    SQLAlchemyRefreshTokenStore,
)
from app.services.refresh_token_service import RefreshTokenService
from tests.factories import create_user


pytestmark = pytest.mark.integration


def create_test_client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def test_signup_route_creates_user_and_sets_refresh_cookie(api_client: TestClient):
    response = api_client.post(
        "/auth/signup",
        headers={"X-Request-ID": "req_signup"},
        json={
            "email": "user@example.com",
            "password": "password123",
            "display_name": "테스터",
        },
    )

    body = response.json()
    assert response.status_code == 201
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["email"] == "user@example.com"
    assert_cookie_common_options(response.headers["set-cookie"])


def test_signup_route_rejects_duplicate_email(api_client: TestClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "password123",
    }
    first_response = api_client.post("/auth/signup", json=payload)
    second_response = api_client.post(
        "/auth/signup",
        headers={"X-Request-ID": "req_signup_duplicate"},
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    body = second_response.json()
    assert body["code"] == "AUTH_EMAIL_ALREADY_EXISTS"
    assert body["request_id"] == "req_signup_duplicate"


def test_login_route_issues_tokens_and_sets_refresh_cookie(
    api_client: TestClient,
    db_session: Session,
):
    create_user(
        db_session,
        email="login@example.com",
        password_hash=PasswordHasher().hash_password("password123"),
    )

    response = api_client.post(
        "/auth/login",
        headers={"X-Request-ID": "req_login"},
        json={
            "email": "login@example.com",
            "password": "password123",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["access_token"]
    assert body["expires_in"] == 900
    assert body["user"]["email"] == "login@example.com"
    assert_cookie_common_options(response.headers["set-cookie"])


def test_login_route_rejects_invalid_credentials(api_client: TestClient):
    response = api_client.post(
        "/auth/login",
        headers={"X-Request-ID": "req_invalid_login"},
        json={
            "email": "missing@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "INVALID_CREDENTIALS"
    assert body["request_id"] == "req_invalid_login"
    assert "password123" not in response.text


def test_current_user_route_returns_user_from_bearer_token(api_client: TestClient):
    signup_response = api_client.post(
        "/auth/signup",
        json={
            "email": "me@example.com",
            "password": "password123",
        },
    )
    access_token = signup_response.json()["access_token"]

    response = api_client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Request-ID": "req_me",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "me@example.com"


def test_current_user_route_requires_bearer_token(api_client: TestClient):
    response = api_client.get(
        "/auth/me",
        headers={"X-Request-ID": "req_me_missing"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_REQUIRED"
    assert body["request_id"] == "req_me_missing"


def test_signup_validation_error_does_not_expose_password_input(
    api_client: TestClient,
):
    response = api_client.post(
        "/auth/signup",
        headers={"X-Request-ID": "req_auth_validation"},
        json={
            "email": "not-email",
            "password": "secret",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "secret" not in response.text


def test_refresh_route_requires_refresh_cookie(api_client: TestClient):
    response = api_client.post(
        "/auth/refresh",
        headers={"X-Request-ID": "req_refresh_missing"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_REQUIRED"
    assert body["request_id"] == "req_refresh_missing"


def test_refresh_route_rotates_refresh_cookie(
    api_client: TestClient,
    db_session: Session,
):
    user = create_user(
        db_session,
        email="refresh@example.com",
        password_hash=PasswordHasher().hash_password("password123"),
    )
    service = RefreshTokenService(SQLAlchemyRefreshTokenStore(db_session))
    issued = service.issue(user, RefreshTokenMetadata(user_agent="pytest"))
    api_client.cookies.set("refresh_token", issued.raw_token)

    response = api_client.post("/auth/refresh")

    db_session.refresh(issued.token)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "refresh@example.com"
    assert issued.token.status == RefreshTokenStatus.ROTATED
    assert issued.token.replaced_by_token_id is not None
    assert response.cookies.get("refresh_token") != issued.raw_token
    assert_cookie_common_options(response.headers["set-cookie"])


def test_logout_route_revokes_refresh_token_and_deletes_cookie(
    api_client: TestClient,
    db_session: Session,
):
    user = create_user(db_session, email="logout@example.com")
    service = RefreshTokenService(SQLAlchemyRefreshTokenStore(db_session))
    issued = service.issue(user, RefreshTokenMetadata())
    api_client.cookies.set("refresh_token", issued.raw_token)

    response = api_client.post("/auth/logout")

    db_session.refresh(issued.token)
    assert response.status_code == 200
    assert response.json() == {"status": "logged_out"}
    assert issued.token.status == RefreshTokenStatus.REVOKED
    assert "refresh_token=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def assert_cookie_common_options(set_cookie_header: str) -> None:
    assert "refresh_token=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Path=/auth" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header
