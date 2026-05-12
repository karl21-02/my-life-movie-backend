from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.user import User


ACCESS_TOKEN_TYPE = "access"


@dataclass(frozen=True)
class IssuedAccessToken:
    access_token: str
    expires_in: int


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    email: str
    token_id: str


class AccessTokenService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def issue(self, user: User) -> IssuedAccessToken:
        if user.id is None:
            raise ValueError("저장된 사용자만 access token을 발급할 수 있습니다.")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(
            minutes=self.settings.access_token_expire_minutes,
        )
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "status": user.status.value,
            "typ": ACCESS_TOKEN_TYPE,
            "iss": self.settings.service_name,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": uuid4().hex,
        }
        token = jwt.encode(
            payload,
            self.settings.access_token_secret_key,
            algorithm=self.settings.access_token_algorithm,
        )
        return IssuedAccessToken(
            access_token=token,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    def verify(self, raw_access_token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                raw_access_token,
                self.settings.access_token_secret_key,
                algorithms=[self.settings.access_token_algorithm],
                issuer=self.settings.service_name,
            )
        except InvalidTokenError as exc:
            raise invalid_access_token_error() from exc

        if payload.get("typ") != ACCESS_TOKEN_TYPE:
            raise invalid_access_token_error()

        try:
            user_id = int(payload["sub"])
            email = str(payload["email"])
            token_id = str(payload["jti"])
        except (KeyError, TypeError, ValueError) as exc:
            raise invalid_access_token_error() from exc

        return AccessTokenClaims(
            user_id=user_id,
            email=email,
            token_id=token_id,
        )


def bearer_token_required_error() -> AppError:
    return AppError(
        status_code=401,
        code="AUTH_REQUIRED",
        title="Auth Required",
        detail="Bearer access token이 필요합니다.",
        type_="auth_required",
    )


def invalid_access_token_error() -> AppError:
    return AppError(
        status_code=401,
        code="INVALID_ACCESS_TOKEN",
        title="Invalid Access Token",
        detail="유효하지 않은 access token입니다.",
        type_="invalid_access_token",
    )
