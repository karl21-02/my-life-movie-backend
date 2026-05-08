from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from app.core.errors import AppError
from app.models.auth_refresh_token import RefreshTokenStatus
from app.models.user import User, UserStatus
from app.repositories.redis_refresh_token_store import RedisRefreshTokenStore
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    RefreshTokenStoreStateChanged,
)
from app.services.refresh_token_service import (
    RefreshTokenService,
    generate_refresh_token,
    hash_refresh_token,
)


pytestmark = pytest.mark.unit


@pytest.fixture()
def redis_store() -> RedisRefreshTokenStore:
    return RedisRefreshTokenStore(
        redis_client=fakeredis.FakeRedis(decode_responses=True),
        key_prefix="service-test",
        retention_seconds=60,
    )


@pytest.fixture()
def refresh_token_service(redis_store: RedisRefreshTokenStore) -> RefreshTokenService:
    return RefreshTokenService(redis_store, expire_days=14)


def test_issue_with_redis_store_stores_only_hash(
    redis_store: RedisRefreshTokenStore,
    refresh_token_service: RefreshTokenService,
):
    user = build_user()

    issued = refresh_token_service.issue(user, RefreshTokenMetadata())
    found_token = redis_store.get_by_hash(hash_refresh_token(issued.raw_token))

    assert found_token is not None
    assert issued.raw_token != found_token.token_hash
    assert found_token.token_hash == hash_refresh_token(issued.raw_token)
    assert found_token.status == RefreshTokenStatus.ACTIVE


def test_rotate_with_redis_store_rejects_reused_token(
    redis_store: RedisRefreshTokenStore,
    refresh_token_service: RefreshTokenService,
):
    issued = refresh_token_service.issue(build_user(), RefreshTokenMetadata())
    rotated = refresh_token_service.rotate(issued.raw_token, RefreshTokenMetadata())

    with pytest.raises(AppError) as exc_info:
        refresh_token_service.rotate(issued.raw_token, RefreshTokenMetadata())

    current_token = redis_store.get_by_hash(hash_refresh_token(issued.raw_token))
    new_token = redis_store.get_by_hash(hash_refresh_token(rotated.raw_token))

    assert exc_info.value.code == "REFRESH_TOKEN_REUSED"
    assert current_token is not None
    assert current_token.status == RefreshTokenStatus.ROTATED
    assert new_token is not None
    assert new_token.status == RefreshTokenStatus.ACTIVE


def test_revoke_with_redis_store_rejects_reused_token(
    refresh_token_service: RefreshTokenService,
):
    issued = refresh_token_service.issue(build_user(), RefreshTokenMetadata())
    refresh_token_service.revoke(issued.raw_token, "LOGOUT")

    with pytest.raises(AppError) as exc_info:
        refresh_token_service.rotate(issued.raw_token, RefreshTokenMetadata())

    assert exc_info.value.code == "REFRESH_TOKEN_REUSED"


def test_store_state_change_is_returned_as_reuse_error(
    refresh_token_service: RefreshTokenService,
    monkeypatch,
):
    issued = refresh_token_service.issue(build_user(), RefreshTokenMetadata())

    def raise_state_changed(**kwargs):
        raise RefreshTokenStoreStateChanged("상태 변경")

    monkeypatch.setattr(refresh_token_service.store, "rotate", raise_state_changed)

    with pytest.raises(AppError) as exc_info:
        refresh_token_service.rotate(issued.raw_token, RefreshTokenMetadata())

    assert exc_info.value.code == "REFRESH_TOKEN_REUSED"


def test_time_expired_token_with_redis_store_is_marked_expired(
    redis_store: RedisRefreshTokenStore,
    refresh_token_service: RefreshTokenService,
):
    raw_token = generate_refresh_token()
    token = redis_store.create(
        user_id=1,
        token_hash=hash_refresh_token(raw_token),
        token_family_id="redis-expired",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        metadata=RefreshTokenMetadata(),
    )

    with pytest.raises(AppError) as exc_info:
        refresh_token_service.rotate(raw_token, RefreshTokenMetadata())

    found_token = redis_store.get_by_hash(hash_refresh_token(raw_token))

    assert found_token is not None
    assert token.id == found_token.id
    assert found_token.status == RefreshTokenStatus.EXPIRED
    assert exc_info.value.code == "REFRESH_TOKEN_EXPIRED"


def build_user() -> User:
    return User(
        id=1,
        email="redis@example.com",
        password_hash="hashed-password",
        status=UserStatus.ACTIVE,
    )
