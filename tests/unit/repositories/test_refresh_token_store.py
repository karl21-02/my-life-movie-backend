from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.auth_refresh_token import RefreshTokenStatus
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    SQLAlchemyRefreshTokenStore,
)
from app.services.refresh_token_service import generate_refresh_token, hash_refresh_token
from tests.factories import create_user


pytestmark = pytest.mark.unit


def test_get_active_by_hash_returns_only_active_token(db_session: Session):
    user = create_user(db_session)
    store = SQLAlchemyRefreshTokenStore(db_session)
    raw_token = generate_refresh_token()
    token = store.create(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        token_family_id="family-active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        metadata=RefreshTokenMetadata(),
    )

    active_token = store.get_active_by_hash(hash_refresh_token(raw_token))

    assert active_token is not None
    assert active_token.id == token.id

    store.revoke(current_token=token, reason="TEST_REVOKE")

    assert store.get_active_by_hash(hash_refresh_token(raw_token)) is None
    assert store.get_by_hash(hash_refresh_token(raw_token)) is not None
    assert token.status == RefreshTokenStatus.REVOKED
