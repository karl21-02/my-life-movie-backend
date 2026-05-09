import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.auth_refresh_token import AuthRefreshToken, RefreshTokenStatus
from app.models.user import User
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    RefreshTokenStore,
    RefreshTokenStoreStateChanged,
)


@dataclass(frozen=True)
class IssuedRefreshToken:
    raw_token: str
    token: AuthRefreshToken


class RefreshTokenService:
    def __init__(
        self,
        store: RefreshTokenStore,
        *,
        expire_days: int | None = None,
    ) -> None:
        self.store = store
        self.expire_days = expire_days or get_settings().refresh_token_expire_days

    def issue(
        self,
        user: User,
        metadata: RefreshTokenMetadata,
    ) -> IssuedRefreshToken:
        if user.id is None:
            raise ValueError("저장된 사용자만 refresh token을 발급할 수 있습니다.")

        raw_token = generate_refresh_token()
        token = self.store.create(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token),
            token_family_id=uuid4().hex,
            expires_at=self._expires_at(),
            metadata=metadata,
        )
        return IssuedRefreshToken(raw_token=raw_token, token=token)

    def rotate(
        self,
        raw_refresh_token: str,
        metadata: RefreshTokenMetadata,
    ) -> IssuedRefreshToken:
        current_token = self.store.get_by_hash(hash_refresh_token(raw_refresh_token))
        if current_token is None:
            raise invalid_refresh_token_error()

        if current_token.status != RefreshTokenStatus.ACTIVE:
            raise refresh_token_reused_error()

        if as_utc(current_token.expires_at) <= datetime.now(timezone.utc):
            self.store.mark_expired(current_token)
            raise expired_refresh_token_error()

        raw_token = generate_refresh_token()
        try:
            new_token = self.store.rotate(
                current_token=current_token,
                new_token_hash=hash_refresh_token(raw_token),
                expires_at=self._expires_at(),
                metadata=metadata,
            )
        except RefreshTokenStoreStateChanged as exc:
            raise refresh_token_reused_error() from exc
        return IssuedRefreshToken(raw_token=raw_token, token=new_token)

    def revoke(
        self,
        raw_refresh_token: str,
        reason: str,
    ) -> AuthRefreshToken:
        current_token = self.store.get_by_hash(hash_refresh_token(raw_refresh_token))
        if current_token is None:
            raise invalid_refresh_token_error()

        if current_token.status != RefreshTokenStatus.ACTIVE:
            raise refresh_token_reused_error()

        try:
            return self.store.revoke(
                current_token=current_token,
                reason=reason,
            )
        except RefreshTokenStoreStateChanged as exc:
            raise refresh_token_reused_error() from exc

    def _expires_at(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=self.expire_days)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_refresh_token: str) -> str:
    return hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def invalid_refresh_token_error() -> AppError:
    return AppError(
        status_code=401,
        code="INVALID_REFRESH_TOKEN",
        title="Invalid Refresh Token",
        detail="유효하지 않은 refresh token입니다.",
        type_="invalid_refresh_token",
    )


def refresh_token_required_error() -> AppError:
    return AppError(
        status_code=401,
        code="AUTH_REQUIRED",
        title="Auth Required",
        detail="refresh token이 필요합니다.",
        type_="auth_required",
    )


def refresh_token_reused_error() -> AppError:
    return AppError(
        status_code=401,
        code="REFRESH_TOKEN_REUSED",
        title="Refresh Token Reused",
        detail="이미 사용되었거나 폐기된 refresh token입니다.",
        type_="refresh_token_reused",
    )


def expired_refresh_token_error() -> AppError:
    return AppError(
        status_code=401,
        code="REFRESH_TOKEN_EXPIRED",
        title="Refresh Token Expired",
        detail="만료된 refresh token입니다.",
        type_="refresh_token_expired",
    )
