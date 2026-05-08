from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.models.user import User, UserRole, UserStatus


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
