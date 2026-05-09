from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.user import UserRole, UserStatus
from app.services.access_token_service import AccessTokenService
from tests.factories import create_user


pytestmark = pytest.mark.unit


def create_settings(expire_minutes: int = 15) -> Settings:
    return Settings(
        service_name="test-service",
        environment="test",
        access_token_secret_key="test-secret-key-with-at-least-32-bytes",
        access_token_expire_minutes=expire_minutes,
    )


def test_issue_access_token_contains_expected_claims(db_session: Session):
    user = create_user(db_session, email="token@example.com")
    service = AccessTokenService(create_settings())

    issued = service.issue(user)
    claims = jwt.decode(
        issued.access_token,
        "test-secret-key-with-at-least-32-bytes",
        algorithms=["HS256"],
        issuer="test-service",
    )

    assert issued.expires_in == 900
    assert claims["sub"] == str(user.id)
    assert claims["email"] == "token@example.com"
    assert claims["role"] == UserRole.USER.value
    assert claims["status"] == UserStatus.ACTIVE.value
    assert claims["typ"] == "access"
    assert claims["jti"]


def test_verify_access_token_returns_user_claims(db_session: Session):
    user = create_user(db_session, email="verify@example.com")
    service = AccessTokenService(create_settings())
    issued = service.issue(user)

    claims = service.verify(issued.access_token)

    assert claims.user_id == user.id
    assert claims.email == "verify@example.com"
    assert claims.token_id


def test_verify_rejects_expired_access_token(db_session: Session):
    user = create_user(db_session, email="expired@example.com")
    service = AccessTokenService(create_settings(expire_minutes=-1))
    issued = service.issue(user)

    with pytest.raises(AppError) as exc_info:
        service.verify(issued.access_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_ACCESS_TOKEN"


def test_verify_rejects_refresh_like_token_type(db_session: Session):
    user = create_user(db_session, email="wrong-type@example.com")
    settings = create_settings()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "typ": "refresh",
        "iss": settings.service_name,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
        "jti": "token-id",
    }
    raw_token = jwt.encode(
        payload,
        settings.access_token_secret_key,
        algorithm=settings.access_token_algorithm,
    )

    with pytest.raises(AppError) as exc_info:
        AccessTokenService(settings).verify(raw_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_ACCESS_TOKEN"
