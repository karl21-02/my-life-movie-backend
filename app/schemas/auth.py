from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole, UserStatus


class AuthSignupRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "password123",
                "display_name": "테스터",
            },
        },
    )

    email: EmailStr = Field(max_length=320, description="로그인에 사용할 이메일입니다.")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="8자 이상 128자 이하 비밀번호입니다.",
    )
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        description="화면에 표시할 사용자 이름입니다.",
    )


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "password123",
            },
        },
    )

    email: EmailStr = Field(max_length=320, description="가입된 이메일입니다.")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="계정 비밀번호입니다.",
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "email": "user@example.com",
                "display_name": "테스터",
                "role": "USER",
                "status": "ACTIVE",
                "created_at": "2026-05-07T00:00:00Z",
                "updated_at": "2026-05-07T00:00:00Z",
            },
        },
    )

    id: int = Field(description="사용자 식별자입니다.")
    email: EmailStr = Field(description="사용자 이메일입니다.")
    display_name: str | None = Field(description="사용자 표시 이름입니다.")
    role: UserRole = Field(description="사용자 권한입니다.")
    status: UserStatus = Field(description="사용자 상태입니다.")
    created_at: datetime = Field(description="생성 일시입니다.")
    updated_at: datetime = Field(description="수정 일시입니다.")


class AuthTokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 900,
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "display_name": "테스터",
                    "role": "USER",
                    "status": "ACTIVE",
                    "created_at": "2026-05-07T00:00:00Z",
                    "updated_at": "2026-05-07T00:00:00Z",
                },
            },
        },
    )

    access_token: str = Field(description="API 호출에 사용할 bearer access token입니다.")
    token_type: str = Field(default="bearer", description="토큰 타입입니다.")
    expires_in: int = Field(description="access token 만료까지 남은 초입니다.", examples=[900])
    user: UserResponse = Field(description="인증된 사용자 정보입니다.")


class CurrentUserResponse(BaseModel):
    user: UserResponse = Field(description="현재 access token의 사용자 정보입니다.")


class LogoutResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "logged_out",
            },
        },
    )

    status: Literal["logged_out"] = Field(
        default="logged_out",
        description="로그아웃 처리 결과입니다.",
    )
