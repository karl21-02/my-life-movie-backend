import pytest
from sqlalchemy.orm import Session

from app.models.user import UserStatus
from app.repositories.user_repository import SQLAlchemyUserRepository


pytestmark = pytest.mark.unit


def test_create_user_normalizes_email_and_defaults_active_status(db_session: Session):
    repository = SQLAlchemyUserRepository(db_session)

    user = repository.create(
        email="  USER@Example.COM  ",
        password_hash="hashed-password",
        display_name="테스터",
    )

    assert user.id is not None
    assert user.email == "user@example.com"
    assert user.status == UserStatus.ACTIVE


def test_get_by_email_uses_normalized_lookup(db_session: Session):
    repository = SQLAlchemyUserRepository(db_session)
    created_user = repository.create(
        email="tester@example.com",
        password_hash="hashed-password",
        display_name=None,
    )

    found_user = repository.get_by_email(" TESTER@EXAMPLE.COM ")

    assert found_user is not None
    assert found_user.id == created_user.id


def test_mark_last_login_updates_timestamp(db_session: Session):
    repository = SQLAlchemyUserRepository(db_session)
    user = repository.create(
        email="tester@example.com",
        password_hash="hashed-password",
        display_name=None,
    )

    updated_user = repository.mark_last_login(user)

    assert updated_user.last_login_at is not None
