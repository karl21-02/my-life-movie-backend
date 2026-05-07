from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app
from app.models.auth_refresh_token import RefreshTokenStatus
from app.models.user import User, UserStatus
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    SQLAlchemyRefreshTokenStore,
)
from app.services.refresh_token_service import RefreshTokenService


def create_test_client(db_session: Session | None = None) -> TestClient:
    app = create_app()

    if db_session is not None:
        def override_db_session():
            yield db_session

        app.dependency_overrides[get_db_session] = override_db_session

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as session:
        yield session


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


def test_refresh_route_requires_refresh_cookie(db_session: Session):
    response = create_test_client(db_session).post(
        "/auth/refresh",
        headers={"X-Request-ID": "req_refresh_missing"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_REQUIRED"
    assert body["request_id"] == "req_refresh_missing"


def test_refresh_route_rotates_refresh_cookie(db_session: Session):
    user = create_active_user(db_session)
    service = RefreshTokenService(SQLAlchemyRefreshTokenStore(db_session))
    issued = service.issue(user, RefreshTokenMetadata(user_agent="pytest"))
    client = create_test_client(db_session)
    client.cookies.set("refresh_token", issued.raw_token)

    response = client.post("/auth/refresh")

    db_session.refresh(issued.token)
    assert response.status_code == 200
    assert response.json() == {"status": "refreshed"}
    assert issued.token.status == RefreshTokenStatus.ROTATED
    assert issued.token.replaced_by_token_id is not None
    assert response.cookies.get("refresh_token") != issued.raw_token
    assert_cookie_common_options(response.headers["set-cookie"])


def test_logout_route_revokes_refresh_token_and_deletes_cookie(db_session: Session):
    user = create_active_user(db_session)
    service = RefreshTokenService(SQLAlchemyRefreshTokenStore(db_session))
    issued = service.issue(user, RefreshTokenMetadata())
    client = create_test_client(db_session)
    client.cookies.set("refresh_token", issued.raw_token)

    response = client.post("/auth/logout")

    db_session.refresh(issued.token)
    assert response.status_code == 200
    assert response.json() == {"status": "logged_out"}
    assert issued.token.status == RefreshTokenStatus.REVOKED
    assert "refresh_token=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def create_active_user(session: Session) -> User:
    user = User(
        email="active@example.com",
        password_hash="hashed-password",
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def assert_cookie_common_options(set_cookie_header: str) -> None:
    assert "refresh_token=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Path=/auth" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header
