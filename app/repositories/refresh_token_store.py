from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_refresh_token import AuthRefreshToken, RefreshTokenStatus


@dataclass(frozen=True)
class RefreshTokenMetadata:
    user_agent: str | None = None
    ip_address: str | None = None


class RefreshTokenStore(Protocol):
    def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        token_family_id: str,
        expires_at: datetime,
        metadata: RefreshTokenMetadata,
        previous_token_id: int | None = None,
    ) -> AuthRefreshToken:
        ...

    def get_by_hash(self, token_hash: str) -> AuthRefreshToken | None:
        ...

    def get_active_by_hash(self, token_hash: str) -> AuthRefreshToken | None:
        ...

    def rotate(
        self,
        *,
        current_token: AuthRefreshToken,
        new_token_hash: str,
        expires_at: datetime,
        metadata: RefreshTokenMetadata,
    ) -> AuthRefreshToken:
        ...

    def revoke(
        self,
        *,
        current_token: AuthRefreshToken,
        reason: str,
    ) -> AuthRefreshToken:
        ...

    def mark_expired(self, current_token: AuthRefreshToken) -> AuthRefreshToken:
        ...


class SQLAlchemyRefreshTokenStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        token_family_id: str,
        expires_at: datetime,
        metadata: RefreshTokenMetadata,
        previous_token_id: int | None = None,
    ) -> AuthRefreshToken:
        token = AuthRefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            token_family_id=token_family_id,
            previous_token_id=previous_token_id,
            expires_at=expires_at,
            user_agent=truncate_or_none(metadata.user_agent, 255),
            ip_address=truncate_or_none(metadata.ip_address, 45),
        )
        self.session.add(token)
        self.session.commit()
        self.session.refresh(token)
        return token

    def get_by_hash(self, token_hash: str) -> AuthRefreshToken | None:
        return self.session.execute(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash),
        ).scalar_one_or_none()

    def get_active_by_hash(self, token_hash: str) -> AuthRefreshToken | None:
        return self.session.execute(
            select(AuthRefreshToken).where(
                AuthRefreshToken.token_hash == token_hash,
                AuthRefreshToken.status == RefreshTokenStatus.ACTIVE,
            ),
        ).scalar_one_or_none()

    def rotate(
        self,
        *,
        current_token: AuthRefreshToken,
        new_token_hash: str,
        expires_at: datetime,
        metadata: RefreshTokenMetadata,
    ) -> AuthRefreshToken:
        now = datetime.now(timezone.utc)
        new_token = AuthRefreshToken(
            user_id=current_token.user_id,
            token_hash=new_token_hash,
            token_family_id=current_token.token_family_id,
            previous_token_id=current_token.id,
            expires_at=expires_at,
            user_agent=truncate_or_none(metadata.user_agent, 255),
            ip_address=truncate_or_none(metadata.ip_address, 45),
        )
        self.session.add(new_token)
        self.session.flush()

        current_token.status = RefreshTokenStatus.ROTATED
        current_token.last_used_at = now
        current_token.replaced_by_token_id = new_token.id

        self.session.commit()
        self.session.refresh(current_token)
        self.session.refresh(new_token)
        return new_token

    def revoke(
        self,
        *,
        current_token: AuthRefreshToken,
        reason: str,
    ) -> AuthRefreshToken:
        now = datetime.now(timezone.utc)
        current_token.status = RefreshTokenStatus.REVOKED
        current_token.revoked_at = now
        current_token.revoked_reason = truncate_or_none(reason, 120)
        self.session.commit()
        self.session.refresh(current_token)
        return current_token

    def mark_expired(self, current_token: AuthRefreshToken) -> AuthRefreshToken:
        current_token.status = RefreshTokenStatus.EXPIRED
        self.session.commit()
        self.session.refresh(current_token)
        return current_token


def truncate_or_none(value: str | None, limit: int) -> str | None:
    if value is None:
        return None

    return value[:limit]
