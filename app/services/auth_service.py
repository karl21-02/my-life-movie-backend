from dataclasses import dataclass

from app.core.errors import AppError
from app.core.security import PasswordHasher
from app.models.auth_refresh_token import AuthRefreshToken
from app.models.user import User, UserStatus
from app.repositories.refresh_token_store import RefreshTokenMetadata
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthLoginRequest,
    AuthSignupRequest,
    AuthTokenResponse,
    CurrentUserResponse,
    UserResponse,
)
from app.services.access_token_service import (
    AccessTokenService,
    invalid_access_token_error,
)
from app.services.refresh_token_service import RefreshTokenService


@dataclass(frozen=True)
class AuthSession:
    response: AuthTokenResponse
    raw_refresh_token: str
    refresh_token: AuthRefreshToken


class AuthService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        access_token_service: AccessTokenService,
        refresh_token_service: RefreshTokenService,
    ) -> None:
        self.user_repository = user_repository
        self.password_hasher = password_hasher
        self.access_token_service = access_token_service
        self.refresh_token_service = refresh_token_service

    def signup(
        self,
        payload: AuthSignupRequest,
        metadata: RefreshTokenMetadata,
    ) -> AuthSession:
        if self.user_repository.get_by_email(str(payload.email)) is not None:
            raise email_already_exists_error()

        user = self.user_repository.create(
            email=str(payload.email),
            password_hash=self.password_hasher.hash_password(payload.password),
            display_name=payload.display_name,
            status=UserStatus.ACTIVE,
        )
        return self._build_session(user, metadata)

    def login(
        self,
        payload: AuthLoginRequest,
        metadata: RefreshTokenMetadata,
    ) -> AuthSession:
        user = self.user_repository.get_by_email(str(payload.email))
        if user is None:
            raise invalid_credentials_error()

        if not self.password_hasher.verify_password(
            payload.password,
            user.password_hash,
        ):
            raise invalid_credentials_error()

        if user.status != UserStatus.ACTIVE:
            raise account_not_active_error()

        self.user_repository.mark_last_login(user)
        return self._build_session(user, metadata)

    def refresh(
        self,
        raw_refresh_token: str,
        metadata: RefreshTokenMetadata,
    ) -> AuthSession:
        issued_refresh_token = self.refresh_token_service.rotate(
            raw_refresh_token,
            metadata,
        )
        user = self.user_repository.get_by_id(issued_refresh_token.token.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise invalid_access_token_error()

        issued_access_token = self.access_token_service.issue(user)
        return AuthSession(
            response=build_auth_token_response(user, issued_access_token),
            raw_refresh_token=issued_refresh_token.raw_token,
            refresh_token=issued_refresh_token.token,
        )

    def get_current_user(self, raw_access_token: str) -> CurrentUserResponse:
        claims = self.access_token_service.verify(raw_access_token)
        user = self.user_repository.get_by_id(claims.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise invalid_access_token_error()

        return CurrentUserResponse(user=UserResponse.model_validate(user))

    def _build_session(
        self,
        user: User,
        metadata: RefreshTokenMetadata,
    ) -> AuthSession:
        issued_access_token = self.access_token_service.issue(user)
        issued_refresh_token = self.refresh_token_service.issue(user, metadata)
        return AuthSession(
            response=build_auth_token_response(user, issued_access_token),
            raw_refresh_token=issued_refresh_token.raw_token,
            refresh_token=issued_refresh_token.token,
        )


def build_auth_token_response(user: User, issued_access_token) -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token=issued_access_token.access_token,
        expires_in=issued_access_token.expires_in,
        user=UserResponse.model_validate(user),
    )


def email_already_exists_error() -> AppError:
    return AppError(
        status_code=409,
        code="AUTH_EMAIL_ALREADY_EXISTS",
        title="Email Already Exists",
        detail="이미 가입된 이메일입니다.",
        type_="auth_email_already_exists",
    )


def invalid_credentials_error() -> AppError:
    return AppError(
        status_code=401,
        code="INVALID_CREDENTIALS",
        title="Invalid Credentials",
        detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        type_="invalid_credentials",
    )


def account_not_active_error() -> AppError:
    return AppError(
        status_code=403,
        code="ACCOUNT_NOT_ACTIVE",
        title="Account Not Active",
        detail="활성화되지 않은 계정입니다.",
        type_="account_not_active",
    )
