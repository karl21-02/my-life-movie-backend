import pytest
from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.models.auth_refresh_token import AuthRefreshToken, RefreshTokenStatus
from app.models.user import User, UserRole, UserStatus


pytestmark = pytest.mark.unit


def test_user_model_defines_basic_auth_columns():
    columns = User.__table__.columns

    assert "id" in columns
    assert "email" in columns
    assert "password_hash" in columns
    assert "display_name" in columns
    assert "role" in columns
    assert "status" in columns
    assert "last_login_at" in columns
    assert "deleted_at" in columns
    assert "created_at" in columns
    assert "updated_at" in columns


def test_user_model_defaults_are_ready_for_email_password_auth():
    assert UserRole.USER.value == "USER"
    assert UserStatus.PENDING.value == "PENDING"

    user = User(
        email="tester@example.com",
        password_hash="hashed-password",
    )

    assert user.email == "tester@example.com"
    assert user.password_hash == "hashed-password"


def test_user_table_can_be_created_from_metadata():
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    assert inspector.has_table("users")
    assert {column["name"] for column in inspector.get_columns("users")} >= {
        "id",
        "email",
        "password_hash",
        "role",
        "status",
    }


def test_refresh_token_model_defines_rotation_columns():
    columns = AuthRefreshToken.__table__.columns

    assert "user_id" in columns
    assert "token_hash" in columns
    assert "token_family_id" in columns
    assert "previous_token_id" in columns
    assert "replaced_by_token_id" in columns
    assert "expires_at" in columns
    assert "last_used_at" in columns
    assert "revoked_at" in columns
    assert "revoked_reason" in columns


def test_refresh_token_status_values_support_rotation_lifecycle():
    assert RefreshTokenStatus.ACTIVE.value == "ACTIVE"
    assert RefreshTokenStatus.ROTATED.value == "ROTATED"
    assert RefreshTokenStatus.REVOKED.value == "REVOKED"
    assert RefreshTokenStatus.EXPIRED.value == "EXPIRED"


def test_refresh_token_table_can_be_created_from_metadata():
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    assert inspector.has_table("auth_refresh_tokens")
    assert {column["name"] for column in inspector.get_columns("auth_refresh_tokens")} >= {
        "id",
        "user_id",
        "token_hash",
        "token_family_id",
        "status",
        "expires_at",
    }
