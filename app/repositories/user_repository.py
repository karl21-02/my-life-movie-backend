from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.models.user import User, UserRole, UserStatus


class UserRepository(Protocol):
    def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None,
        role: UserRole = UserRole.USER,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> User:
        ...

    def get_by_id(self, user_id: int) -> User | None:
        ...

    def get_by_email(self, email: str) -> User | None:
        ...

    def mark_last_login(self, user: User) -> User:
        ...


class SQLAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None,
        role: UserRole = UserRole.USER,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> User:
        user = User(
            email=normalize_email(email),
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            status=status,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.execute(
            select(User).where(User.email == normalize_email(email)),
        ).scalar_one_or_none()

    def mark_last_login(self, user: User) -> User:
        user.last_login_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(user)
        return user
