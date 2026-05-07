from fastapi import APIRouter, Depends, status

from app.schemas.auth import (
    AuthLoginRequest,
    AuthSignupRequest,
    AuthTokenResponse,
    CurrentUserResponse,
)
from app.services.auth_service import AuthService, get_auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
async def signup(
    payload: AuthSignupRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    return await auth_service.signup(payload)


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="로그인",
)
async def login(
    payload: AuthLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    return await auth_service.login(payload)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="현재 사용자 조회",
)
async def get_current_user(
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUserResponse:
    return await auth_service.get_current_user()
