import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import PasswordHasher
from app.models.user import UserStatus
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    SQLAlchemyRefreshTokenStore,
)
from app.repositories.user_repository import SQLAlchemyUserRepository
from app.schemas.auth import AuthLoginRequest, AuthSignupRequest
from app.services.access_token_service import AccessTokenService
from app.services.auth_service import AuthService
from app.services.refresh_token_service import RefreshTokenService
from tests.factories import create_user


pytestmark = pytest.mark.unit


def create_auth_service(db_session: Session) -> AuthService:
    return AuthService(
        user_repository=SQLAlchemyUserRepository(db_session),
        password_hasher=PasswordHasher(),
        access_token_service=AccessTokenService(),
        refresh_token_service=RefreshTokenService(
            SQLAlchemyRefreshTokenStore(db_session),
        ),
    )


def test_signup_creates_active_user_and_auth_session(db_session: Session):
    service = create_auth_service(db_session)

    session = service.signup(
        AuthSignupRequest(
            email="new@example.com",
            password="password123",
            display_name="신규 사용자",
        ),
        RefreshTokenMetadata(user_agent="pytest"),
    )

    assert session.response.access_token
    assert session.response.expires_in == 900
    assert session.response.user.email == "new@example.com"
    assert session.raw_refresh_token
    assert session.refresh_token.user_agent == "pytest"


def test_signup_rejects_duplicate_email(db_session: Session):
    service = create_auth_service(db_session)
    payload = AuthSignupRequest(
        email="dup@example.com",
        password="password123",
        display_name=None,
    )
    service.signup(payload, RefreshTokenMetadata())

    with pytest.raises(AppError) as exc_info:
        service.signup(payload, RefreshTokenMetadata())

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "AUTH_EMAIL_ALREADY_EXISTS"


def test_login_issues_auth_session_and_updates_last_login(db_session: Session):
    password_hasher = PasswordHasher()
    user = create_user(
        db_session,
        email="login@example.com",
        password_hash=password_hasher.hash_password("password123"),
    )
    service = create_auth_service(db_session)

    session = service.login(
        AuthLoginRequest(email="login@example.com", password="password123"),
        RefreshTokenMetadata(ip_address="127.0.0.1"),
    )

    db_session.refresh(user)
    assert session.response.access_token
    assert session.raw_refresh_token
    assert user.last_login_at is not None


def test_login_rejects_wrong_password(db_session: Session):
    password_hasher = PasswordHasher()
    create_user(
        db_session,
        email="wrong@example.com",
        password_hash=password_hasher.hash_password("password123"),
    )
    service = create_auth_service(db_session)

    with pytest.raises(AppError) as exc_info:
        service.login(
            AuthLoginRequest(email="wrong@example.com", password="wrong-password"),
            RefreshTokenMetadata(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_CREDENTIALS"


def test_login_rejects_inactive_user(db_session: Session):
    password_hasher = PasswordHasher()
    create_user(
        db_session,
        email="inactive@example.com",
        password_hash=password_hasher.hash_password("password123"),
        status=UserStatus.DISABLED,
    )
    service = create_auth_service(db_session)

    with pytest.raises(AppError) as exc_info:
        service.login(
            AuthLoginRequest(email="inactive@example.com", password="password123"),
            RefreshTokenMetadata(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "ACCOUNT_NOT_ACTIVE"


def test_get_current_user_returns_user_from_access_token(db_session: Session):
    service = create_auth_service(db_session)
    session = service.signup(
        AuthSignupRequest(
            email="me@example.com",
            password="password123",
            display_name=None,
        ),
        RefreshTokenMetadata(),
    )

    current_user = service.get_current_user(session.response.access_token)

    assert current_user.user.email == "me@example.com"


def test_refresh_rotates_refresh_token_and_issues_access_token(db_session: Session):
    service = create_auth_service(db_session)
    session = service.signup(
        AuthSignupRequest(
            email="refresh-service@example.com",
            password="password123",
            display_name=None,
        ),
        RefreshTokenMetadata(),
    )

    refreshed = service.refresh(session.raw_refresh_token, RefreshTokenMetadata())

    db_session.refresh(session.refresh_token)
    assert refreshed.response.access_token
    assert refreshed.raw_refresh_token != session.raw_refresh_token
    assert session.refresh_token.replaced_by_token_id == refreshed.refresh_token.id
