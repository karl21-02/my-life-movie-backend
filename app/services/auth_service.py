from app.core.errors import AppError
from app.schemas.auth import (
    AuthLoginRequest,
    AuthSignupRequest,
    AuthTokenResponse,
    CurrentUserResponse,
)


class AuthService:
    async def signup(self, payload: AuthSignupRequest) -> AuthTokenResponse:
        raise auth_not_implemented_error("회원가입 로직은 아직 구현되지 않았습니다.")

    async def login(self, payload: AuthLoginRequest) -> AuthTokenResponse:
        raise auth_not_implemented_error("로그인 로직은 아직 구현되지 않았습니다.")

    async def get_current_user(self) -> CurrentUserResponse:
        raise auth_not_implemented_error("현재 사용자 조회 로직은 아직 구현되지 않았습니다.")


def auth_not_implemented_error(detail: str) -> AppError:
    return AppError(
        status_code=501,
        code="AUTH_NOT_IMPLEMENTED",
        title="Auth Not Implemented",
        detail=detail,
        type_="auth_not_implemented",
    )


def get_auth_service() -> AuthService:
    return AuthService()
