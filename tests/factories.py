from sqlalchemy.orm import Session

from app.models.user import User, UserStatus


def create_user(
    session: Session,
    *,
    email: str = "tester@example.com",
    password_hash: str = "hashed-password",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        status=status,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
