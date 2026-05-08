import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.redis_refresh_token_store import RedisRefreshTokenStore
from app.repositories.refresh_token_store import SQLAlchemyRefreshTokenStore
from app.routers.auth import build_refresh_token_store


pytestmark = pytest.mark.unit


def test_build_refresh_token_store_uses_mysql_by_default(db_session: Session):
    store = build_refresh_token_store(
        settings=Settings(refresh_token_store="mysql"),
        db_session=db_session,
    )

    assert isinstance(store, SQLAlchemyRefreshTokenStore)


def test_build_refresh_token_store_uses_redis_when_configured(db_session: Session):
    store = build_refresh_token_store(
        settings=Settings(
            refresh_token_store="redis",
            redis_url="redis://localhost:6379/9",
        ),
        db_session=db_session,
    )

    assert isinstance(store, RedisRefreshTokenStore)


def test_build_refresh_token_store_requires_redis_url(db_session: Session):
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        build_refresh_token_store(
            settings=Settings(refresh_token_store="redis"),
            db_session=db_session,
        )


def test_build_refresh_token_store_rejects_unknown_store(db_session: Session):
    with pytest.raises(RuntimeError, match="지원하지 않는"):
        build_refresh_token_store(
            settings=Settings(refresh_token_store="unknown"),
            db_session=db_session,
        )
