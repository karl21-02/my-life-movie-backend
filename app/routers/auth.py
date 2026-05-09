from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.openapi import (
    ACCOUNT_NOT_ACTIVE_RESPONSE,
    AUTH_CONFLICT_RESPONSE,
    AUTH_REQUIRED_RESPONSE,
    COMMON_PROBLEM_RESPONSES,
    DELETE_REFRESH_COOKIE_HEADER,
    INVALID_CREDENTIALS_RESPONSE,
    SET_REFRESH_COOKIE_HEADER,
)
from app.core.security import PasswordHasher
from app.db.session import get_db_session
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    RefreshTokenStore,
    SQLAlchemyRefreshTokenStore,
)
from app.repositories.redis_refresh_token_store import RedisRefreshTokenStore
from app.repositories.user_repository import SQLAlchemyUserRepository
from app.schemas.auth import (
    AuthLoginRequest,
    AuthSignupRequest,
    AuthTokenResponse,
    CurrentUserResponse,
    LogoutResponse,
)
from app.services.access_token_service import (
    AccessTokenService,
    bearer_token_required_error,
)
from app.services.auth_service import AuthService
from app.services.refresh_token_service import (
    RefreshTokenService,
    refresh_token_required_error,
)


router = APIRouter(prefix="/auth", tags=["인증"])

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="`/auth/login` 또는 `/auth/refresh` 응답의 access token을 사용합니다.",
)

RefreshTokenCookie = Annotated[
    str | None,
    Cookie(
        alias="refresh_token",
        description="로그인 또는 refresh 성공 시 발급되는 HttpOnly refresh token cookie입니다.",
    ),
]

def get_auth_service(
    db_session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    refresh_token_store = build_refresh_token_store(
        settings=settings,
        db_session=db_session,
    )
    return AuthService(
        user_repository=SQLAlchemyUserRepository(db_session),
        password_hasher=PasswordHasher(),
        access_token_service=AccessTokenService(settings),
        refresh_token_service=RefreshTokenService(
            refresh_token_store,
            expire_days=settings.refresh_token_expire_days,
        ),
    )


def get_refresh_token_service(
    db_session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> RefreshTokenService:
    return RefreshTokenService(
        build_refresh_token_store(
            settings=settings,
            db_session=db_session,
        ),
        expire_days=settings.refresh_token_expire_days,
    )


def build_refresh_token_store(
    *,
    settings: Settings,
    db_session: Session,
) -> RefreshTokenStore:
    if settings.refresh_token_store == "redis":
        if settings.redis_url is None:
            raise RuntimeError("REFRESH_TOKEN_STORE=redis 설정에는 REDIS_URL이 필요합니다.")

        return RedisRefreshTokenStore(
            redis_url=settings.redis_url,
            retention_seconds=settings.refresh_token_redis_retention_seconds,
        )

    if settings.refresh_token_store == "mysql":
        return SQLAlchemyRefreshTokenStore(db_session)

    raise RuntimeError(
        f"지원하지 않는 refresh token 저장소입니다: {settings.refresh_token_store}",
    )


def build_refresh_token_metadata(request: Request) -> RefreshTokenMetadata:
    client_host = request.client.host if request.client else None
    return RefreshTokenMetadata(
        user_agent=request.headers.get("user-agent"),
        ip_address=client_host,
    )


def set_refresh_token_cookie(
    response: Response,
    raw_refresh_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=raw_refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=settings.refresh_token_cookie_path,
        httponly=True,
        secure=settings.refresh_token_cookie_secure,
        samesite=settings.refresh_token_cookie_samesite,
    )


def delete_refresh_token_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_token_cookie_name,
        path=settings.refresh_token_cookie_path,
        secure=settings.refresh_token_cookie_secure,
        httponly=True,
        samesite=settings.refresh_token_cookie_samesite,
    )


def extract_bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is None:
        raise bearer_token_required_error()

    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise bearer_token_required_error()

    return credentials.credentials


@router.post(
    "/signup",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description=(
        "이메일과 비밀번호로 사용자를 생성하고 access token을 응답합니다. "
        "refresh token은 응답 body가 아니라 `HttpOnly` cookie로 설정합니다."
    ),
    responses={
        201: {
            "description": "회원가입 성공입니다.",
            "headers": {
                "Set-Cookie": SET_REFRESH_COOKIE_HEADER,
            },
        },
        409: AUTH_CONFLICT_RESPONSE,
        **COMMON_PROBLEM_RESPONSES,
    },
)
async def signup(
    payload: AuthSignupRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    session = auth_service.signup(payload, build_refresh_token_metadata(request))
    set_refresh_token_cookie(response, session.raw_refresh_token, settings)
    return session.response


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="로그인",
    description=(
        "이메일과 비밀번호를 검증하고 access token을 응답합니다. "
        "refresh token은 응답 body가 아니라 `HttpOnly` cookie로 설정합니다."
    ),
    responses={
        200: {
            "description": "로그인 성공입니다.",
            "headers": {
                "Set-Cookie": SET_REFRESH_COOKIE_HEADER,
            },
        },
        401: INVALID_CREDENTIALS_RESPONSE,
        **COMMON_PROBLEM_RESPONSES,
    },
)
async def login(
    payload: AuthLoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    session = auth_service.login(payload, build_refresh_token_metadata(request))
    set_refresh_token_cookie(response, session.raw_refresh_token, settings)
    return session.response


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="현재 사용자 조회",
    description="Authorization bearer access token으로 현재 사용자를 조회합니다.",
    responses={
        401: AUTH_REQUIRED_RESPONSE,
        403: ACCOUNT_NOT_ACTIVE_RESPONSE,
        **COMMON_PROBLEM_RESPONSES,
    },
)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUserResponse:
    return auth_service.get_current_user(extract_bearer_token(credentials))


@router.post(
    "/refresh",
    response_model=AuthTokenResponse,
    summary="refresh token 회전",
    description=(
        "`refresh_token` HttpOnly cookie를 검증하고 새 access token과 새 refresh token cookie를 발급합니다. "
        "성공 시 기존 refresh token은 `ROTATED` 상태가 되어 재사용할 수 없습니다."
    ),
    responses={
        200: {
            "description": "refresh token 회전 성공입니다.",
            "headers": {
                "Set-Cookie": SET_REFRESH_COOKIE_HEADER,
            },
        },
        401: AUTH_REQUIRED_RESPONSE,
        **COMMON_PROBLEM_RESPONSES,
    },
)
async def refresh_token(
    request: Request,
    response: Response,
    raw_refresh_token: RefreshTokenCookie = None,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    raw_refresh_token = raw_refresh_token or request.cookies.get(
        settings.refresh_token_cookie_name,
    )
    if raw_refresh_token is None:
        raise refresh_token_required_error()

    session = auth_service.refresh(
        raw_refresh_token,
        build_refresh_token_metadata(request),
    )
    set_refresh_token_cookie(response, session.raw_refresh_token, settings)
    return session.response


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="refresh token 폐기",
    description=(
        "현재 `refresh_token` cookie를 `REVOKED` 처리하고 cookie를 삭제합니다. "
        "이미 만료되었거나 없는 cookie여도 클라이언트 로그아웃은 성공 응답으로 정리합니다."
    ),
    responses={
        200: {
            "description": "로그아웃 성공입니다.",
            "headers": {
                "Set-Cookie": DELETE_REFRESH_COOKIE_HEADER,
            },
        },
        **COMMON_PROBLEM_RESPONSES,
    },
)
async def logout(
    request: Request,
    response: Response,
    raw_refresh_token: RefreshTokenCookie = None,
    settings: Settings = Depends(get_settings),
    refresh_token_service: RefreshTokenService = Depends(get_refresh_token_service),
) -> LogoutResponse:
    raw_refresh_token = raw_refresh_token or request.cookies.get(
        settings.refresh_token_cookie_name,
    )
    if raw_refresh_token is not None:
        try:
            refresh_token_service.revoke(raw_refresh_token, "LOGOUT")
        except AppError as exc:
            if exc.status_code != 401:
                raise

    delete_refresh_token_cookie(response, settings)
    return LogoutResponse()
