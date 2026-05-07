from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError
from app.db.base import Base
from app.models.auth_refresh_token import AuthRefreshToken, RefreshTokenStatus
from app.models.user import User, UserStatus
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    SQLAlchemyRefreshTokenStore,
)
from app.services.refresh_token_service import (
    RefreshTokenService,
    generate_refresh_token,
    hash_refresh_token,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as db_session:
        yield db_session


def create_user(session: Session) -> User:
    user = User(
        email="tester@example.com",
        password_hash="hashed-password",
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_service(session: Session) -> RefreshTokenService:
    return RefreshTokenService(
        SQLAlchemyRefreshTokenStore(session),
        expire_days=14,
    )


def test_issue_stores_only_refresh_token_hash(session: Session):
    user = create_user(session)
    service = create_service(session)

    issued = service.issue(
        user,
        RefreshTokenMetadata(user_agent="pytest", ip_address="127.0.0.1"),
    )

    assert issued.raw_token
    assert issued.raw_token != issued.token.token_hash
    assert issued.token.token_hash == hash_refresh_token(issued.raw_token)
    assert len(issued.token.token_hash) == 64
    assert issued.token.status == RefreshTokenStatus.ACTIVE
    assert issued.token.user_agent == "pytest"


def test_rotate_marks_current_token_and_links_new_token(session: Session):
    user = create_user(session)
    service = create_service(session)
    issued = service.issue(user, RefreshTokenMetadata(user_agent="first"))

    rotated = service.rotate(
        issued.raw_token,
        RefreshTokenMetadata(user_agent="second"),
    )

    session.refresh(issued.token)
    assert issued.token.status == RefreshTokenStatus.ROTATED
    assert issued.token.replaced_by_token_id == rotated.token.id
    assert rotated.token.status == RefreshTokenStatus.ACTIVE
    assert rotated.token.previous_token_id == issued.token.id
    assert rotated.token.token_family_id == issued.token.token_family_id
    assert rotated.raw_token != issued.raw_token
    assert rotated.token.user_agent == "second"


def test_rotated_token_reuse_is_rejected(session: Session):
    user = create_user(session)
    service = create_service(session)
    issued = service.issue(user, RefreshTokenMetadata())
    service.rotate(issued.raw_token, RefreshTokenMetadata())

    with pytest.raises(AppError) as exc_info:
        service.rotate(issued.raw_token, RefreshTokenMetadata())

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "REFRESH_TOKEN_REUSED"


def test_revoked_token_reuse_is_rejected(session: Session):
    user = create_user(session)
    service = create_service(session)
    issued = service.issue(user, RefreshTokenMetadata())
    service.revoke(issued.raw_token, "LOGOUT")

    with pytest.raises(AppError) as exc_info:
        service.rotate(issued.raw_token, RefreshTokenMetadata())

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "REFRESH_TOKEN_REUSED"


def test_expired_status_token_reuse_is_rejected(session: Session):
    user = create_user(session)
    store = SQLAlchemyRefreshTokenStore(session)
    service = RefreshTokenService(store, expire_days=14)
    raw_token = generate_refresh_token()
    token = store.create(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        token_family_id="family-expired",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(),
    )
    token.status = RefreshTokenStatus.EXPIRED
    session.commit()

    with pytest.raises(AppError) as exc_info:
        service.rotate(raw_token, RefreshTokenMetadata())

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "REFRESH_TOKEN_REUSED"


def test_active_but_time_expired_token_is_marked_expired(session: Session):
    user = create_user(session)
    store = SQLAlchemyRefreshTokenStore(session)
    service = RefreshTokenService(store, expire_days=14)
    raw_token = generate_refresh_token()
    token = store.create(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        token_family_id="family-time-expired",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        metadata=RefreshTokenMetadata(),
    )

    with pytest.raises(AppError) as exc_info:
        service.rotate(raw_token, RefreshTokenMetadata())

    session.refresh(token)
    assert token.status == RefreshTokenStatus.EXPIRED
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "REFRESH_TOKEN_EXPIRED"


def test_revoke_marks_active_token_as_revoked(session: Session):
    user = create_user(session)
    service = create_service(session)
    issued = service.issue(user, RefreshTokenMetadata())

    revoked = service.revoke(issued.raw_token, "LOGOUT")

    assert revoked.status == RefreshTokenStatus.REVOKED
    assert revoked.revoked_reason == "LOGOUT"
    assert revoked.revoked_at is not None
