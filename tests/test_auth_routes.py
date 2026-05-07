from fastapi.testclient import TestClient

from app.main import create_app


def create_test_client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def test_signup_route_exposes_placeholder_problem_details():
    response = create_test_client().post(
        "/auth/signup",
        headers={"X-Request-ID": "req_signup"},
        json={
            "email": "user@example.com",
            "password": "password123",
            "display_name": "테스터",
        },
    )

    assert response.status_code == 501
    assert response.json() == {
        "type": "auth_not_implemented",
        "title": "Auth Not Implemented",
        "status": 501,
        "detail": "회원가입 로직은 아직 구현되지 않았습니다.",
        "instance": "/auth/signup",
        "code": "AUTH_NOT_IMPLEMENTED",
        "request_id": "req_signup",
        "errors": [],
    }


def test_login_route_exposes_placeholder_problem_details():
    response = create_test_client().post(
        "/auth/login",
        headers={"X-Request-ID": "req_login"},
        json={
            "email": "user@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 501
    body = response.json()
    assert body["code"] == "AUTH_NOT_IMPLEMENTED"
    assert body["request_id"] == "req_login"
    assert body["instance"] == "/auth/login"


def test_current_user_route_exposes_placeholder_problem_details():
    response = create_test_client().get(
        "/auth/me",
        headers={"X-Request-ID": "req_me"},
    )

    assert response.status_code == 501
    body = response.json()
    assert body["code"] == "AUTH_NOT_IMPLEMENTED"
    assert body["request_id"] == "req_me"
    assert body["instance"] == "/auth/me"


def test_signup_validation_error_does_not_expose_password_input():
    response = create_test_client().post(
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
