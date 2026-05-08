from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SQLAlchemyEnum,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DELETED = "DELETED"


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_status", "status"),
        Index("ix_users_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SQLAlchemyEnum(UserRole, name="user_role", native_enum=False, length=32),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLAlchemyEnum(UserStatus, name="user_status", native_enum=False, length=32),
        nullable=False,
        default=UserStatus.PENDING,
        server_default=UserStatus.PENDING.value,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
