from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import PasswordHasher
from app.db.session import get_db_session
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    SQLAlchemyRefreshTokenStore,
)
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


router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    db_session: Session = Depends(get_db_session),
) -> AuthService:
    refresh_token_store = SQLAlchemyRefreshTokenStore(db_session)
    return AuthService(
        user_repository=SQLAlchemyUserRepository(db_session),
        password_hasher=PasswordHasher(),
        access_token_service=AccessTokenService(),
        refresh_token_service=RefreshTokenService(refresh_token_store),
    )


def get_refresh_token_service(
    db_session: Session = Depends(get_db_session),
) -> RefreshTokenService:
    return RefreshTokenService(SQLAlchemyRefreshTokenStore(db_session))


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


def extract_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise bearer_token_required_error()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise bearer_token_required_error()

    return token


@router.post(
    "/signup",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
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
)
async def get_current_user(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUserResponse:
    return auth_service.get_current_user(extract_bearer_token(authorization))


@router.post(
    "/refresh",
    response_model=AuthTokenResponse,
    summary="refresh token 회전",
)
async def refresh_token(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    raw_refresh_token = request.cookies.get(settings.refresh_token_cookie_name)
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
)
async def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    refresh_token_service: RefreshTokenService = Depends(get_refresh_token_service),
) -> LogoutResponse:
    raw_refresh_token = request.cookies.get(settings.refresh_token_cookie_name)
    if raw_refresh_token is not None:
        try:
            refresh_token_service.revoke(raw_refresh_token, "LOGOUT")
        except AppError as exc:
            if exc.status_code != 401:
                raise

    delete_refresh_token_cookie(response, settings)
    return LogoutResponse()
