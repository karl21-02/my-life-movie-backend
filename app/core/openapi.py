from typing import Any

from app.schemas.errors import ProblemDetailsResponse


API_DESCRIPTION = """
My Life Movie 백엔드 API 문서입니다.

인증 API는 이메일/비밀번호 기반 회원가입과 로그인, bearer access token 검증,
refresh token 회전, 로그아웃을 제공합니다.

에러 응답은 Problem Details 스타일로 통일하며, 모든 응답에는 문제 추적을 위한
`request_id`가 포함됩니다. refresh token은 `HttpOnly` cookie로만 전달하고,
DB 또는 Redis 저장소에는 원문이 아닌 `sha256` hash만 저장합니다.
"""

OPENAPI_TAGS = [
    {
        "name": "시스템",
        "description": "서비스 상태 확인과 운영 기본 엔드포인트입니다.",
    },
    {
        "name": "인증",
        "description": (
            "회원가입, 로그인, 현재 사용자 조회, refresh token 회전, 로그아웃 API입니다. "
            "`/auth/me`는 Authorization bearer token이 필요하고, "
            "`/auth/refresh`, `/auth/logout`은 `refresh_token` HttpOnly cookie를 사용합니다."
        ),
    },
]

SET_REFRESH_COOKIE_HEADER = {
    "description": (
        "`refresh_token` HttpOnly cookie입니다. 로컬은 Secure=false, 운영은 Secure=true로 설정합니다."
    ),
    "schema": {
        "type": "string",
        "example": (
            "refresh_token=raw-token; HttpOnly; Max-Age=1209600; "
            "Path=/auth; SameSite=lax"
        ),
    },
}

DELETE_REFRESH_COOKIE_HEADER = {
    "description": "`refresh_token` cookie 삭제 헤더입니다.",
    "schema": {
        "type": "string",
        "example": "refresh_token=; HttpOnly; Max-Age=0; Path=/auth; SameSite=lax",
    },
}

VALIDATION_ERROR_EXAMPLE = {
    "type": "validation_error",
    "title": "Validation Error",
    "status": 422,
    "detail": "Request validation failed.",
    "instance": "/auth/login",
    "code": "VALIDATION_ERROR",
    "request_id": "req_123",
    "errors": [
        {
            "loc": ["body", "email"],
            "msg": "value is not a valid email address",
            "type": "value_error",
        },
    ],
}

AUTH_REQUIRED_EXAMPLE = {
    "type": "auth_required",
    "title": "Auth Required",
    "status": 401,
    "detail": "인증 정보가 필요합니다.",
    "instance": "/auth/me",
    "code": "AUTH_REQUIRED",
    "request_id": "req_123",
    "errors": [],
}

INVALID_CREDENTIALS_EXAMPLE = {
    "type": "invalid_credentials",
    "title": "Invalid Credentials",
    "status": 401,
    "detail": "이메일 또는 비밀번호가 올바르지 않습니다.",
    "instance": "/auth/login",
    "code": "INVALID_CREDENTIALS",
    "request_id": "req_123",
    "errors": [],
}

EMAIL_CONFLICT_EXAMPLE = {
    "type": "auth_email_already_exists",
    "title": "Email Already Exists",
    "status": 409,
    "detail": "이미 가입된 이메일입니다.",
    "instance": "/auth/signup",
    "code": "AUTH_EMAIL_ALREADY_EXISTS",
    "request_id": "req_123",
    "errors": [],
}

INTERNAL_SERVER_ERROR_EXAMPLE = {
    "type": "internal_server_error",
    "title": "Internal Server Error",
    "status": 500,
    "detail": "Internal server error.",
    "instance": "/auth/login",
    "code": "INTERNAL_SERVER_ERROR",
    "request_id": "req_123",
    "errors": [],
}


def problem_response(
    *,
    description: str,
    example: dict[str, Any],
) -> dict[str, Any]:
    return {
        "model": ProblemDetailsResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": example,
            },
        },
    }


COMMON_PROBLEM_RESPONSES = {
    422: problem_response(
        description="요청 본문, 헤더, 쿠키 검증 실패입니다.",
        example=VALIDATION_ERROR_EXAMPLE,
    ),
    500: problem_response(
        description="예상하지 못한 서버 오류입니다.",
        example=INTERNAL_SERVER_ERROR_EXAMPLE,
    ),
}

AUTH_REQUIRED_RESPONSE = problem_response(
    description="인증 정보가 없거나 유효하지 않습니다.",
    example=AUTH_REQUIRED_EXAMPLE,
)

AUTH_CONFLICT_RESPONSE = problem_response(
    description="이미 존재하는 이메일처럼 요청이 현재 리소스 상태와 충돌합니다.",
    example=EMAIL_CONFLICT_EXAMPLE,
)

INVALID_CREDENTIALS_RESPONSE = problem_response(
    description="이메일 또는 비밀번호가 올바르지 않습니다.",
    example=INVALID_CREDENTIALS_EXAMPLE,
)

ACCOUNT_NOT_ACTIVE_RESPONSE = problem_response(
    description="계정이 비활성 상태입니다.",
    example={
        "type": "account_not_active",
        "title": "Account Not Active",
        "status": 403,
        "detail": "활성화되지 않은 계정입니다.",
        "instance": "/auth/me",
        "code": "ACCOUNT_NOT_ACTIVE",
        "request_id": "req_123",
        "errors": [],
    },
)
