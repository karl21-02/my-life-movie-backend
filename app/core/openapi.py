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
