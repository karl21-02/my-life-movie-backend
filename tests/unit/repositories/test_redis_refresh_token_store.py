from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from app.models.auth_refresh_token import RefreshTokenStatus
from app.repositories.redis_refresh_token_store import RedisRefreshTokenStore
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    RefreshTokenStoreStateChanged,
)


pytestmark = pytest.mark.unit


@pytest.fixture()
def redis_store() -> RedisRefreshTokenStore:
    return RedisRefreshTokenStore(
        redis_client=fakeredis.FakeRedis(decode_responses=True),
        key_prefix="test",
        retention_seconds=60,
    )


def test_create_and_get_by_hash_returns_refresh_token(redis_store: RedisRefreshTokenStore):
    token = redis_store.create(
        user_id=1,
        token_hash="a" * 64,
        token_family_id="family-redis",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(
            user_agent="pytest",
            ip_address="127.0.0.1",
        ),
    )

    found_token = redis_store.get_by_hash("a" * 64)

    assert found_token is not None
    assert found_token.id == token.id
    assert found_token.status == RefreshTokenStatus.ACTIVE
    assert found_token.user_agent == "pytest"
    assert found_token.ip_address == "127.0.0.1"


def test_get_active_by_hash_returns_only_active_token(
    redis_store: RedisRefreshTokenStore,
):
    token_hash = "b" * 64
    token = redis_store.create(
        user_id=1,
        token_hash=token_hash,
        token_family_id="family-active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(),
    )

    assert redis_store.get_active_by_hash(token_hash) is not None

    redis_store.revoke(current_token=token, reason="TEST_REVOKE")

    assert redis_store.get_active_by_hash(token_hash) is None
    assert redis_store.get_by_hash(token_hash) is not None


def test_rotate_marks_current_token_and_links_new_token(
    redis_store: RedisRefreshTokenStore,
):
    current_token_hash = "c" * 64
    new_token_hash = "d" * 64
    current_token = redis_store.create(
        user_id=1,
        token_hash=current_token_hash,
        token_family_id="family-rotate",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(user_agent="first"),
    )

    new_token = redis_store.rotate(
        current_token=current_token,
        new_token_hash=new_token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(user_agent="second"),
    )

    rotated_token = redis_store.get_by_hash(current_token_hash)

    assert rotated_token is not None
    assert rotated_token.status == RefreshTokenStatus.ROTATED
    assert rotated_token.last_used_at is not None
    assert rotated_token.replaced_by_token_id == new_token.id
    assert new_token.status == RefreshTokenStatus.ACTIVE
    assert new_token.previous_token_id == current_token.id
    assert new_token.token_family_id == current_token.token_family_id
    assert new_token.user_agent == "second"


def test_rotate_rejects_stale_active_snapshot(redis_store: RedisRefreshTokenStore):
    current_token_hash = "1" * 64
    current_token = redis_store.create(
        user_id=1,
        token_hash=current_token_hash,
        token_family_id="family-stale",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(),
    )
    stale_snapshot = redis_store.get_by_hash(current_token_hash)
    redis_store.rotate(
        current_token=current_token,
        new_token_hash="2" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(),
    )

    with pytest.raises(RefreshTokenStoreStateChanged):
        redis_store.rotate(
            current_token=stale_snapshot,
            new_token_hash="3" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            metadata=RefreshTokenMetadata(),
        )


def test_revoke_marks_token_as_revoked(redis_store: RedisRefreshTokenStore):
    token = redis_store.create(
        user_id=1,
        token_hash="e" * 64,
        token_family_id="family-revoke",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(),
    )

    revoked_token = redis_store.revoke(
        current_token=token,
        reason="LOGOUT",
    )

    found_token = redis_store.get_by_hash("e" * 64)

    assert revoked_token.status == RefreshTokenStatus.REVOKED
    assert revoked_token.revoked_reason == "LOGOUT"
    assert revoked_token.revoked_at is not None
    assert found_token is not None
    assert found_token.status == RefreshTokenStatus.REVOKED


def test_mark_expired_keeps_token_for_reuse_detection(
    redis_store: RedisRefreshTokenStore,
):
    token = redis_store.create(
        user_id=1,
        token_hash="f" * 64,
        token_family_id="family-expired",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        metadata=RefreshTokenMetadata(),
    )

    expired_token = redis_store.mark_expired(token)
    found_token = redis_store.get_by_hash("f" * 64)

    assert expired_token.status == RefreshTokenStatus.EXPIRED
    assert found_token is not None
    assert found_token.status == RefreshTokenStatus.EXPIRED
