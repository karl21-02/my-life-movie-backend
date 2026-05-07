from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProblemErrorItem(BaseModel):
    loc: list[str | int] | None = Field(
        default=None,
        description="오류가 발생한 입력 위치입니다.",
        examples=[["body", "email"]],
    )
    msg: str | None = Field(
        default=None,
        description="검증 오류 메시지입니다.",
        examples=["value is not a valid email address"],
    )
    type: str | None = Field(
        default=None,
        description="프레임워크 또는 도메인 오류 타입입니다.",
        examples=["value_error"],
    )


class ProblemDetailsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
            },
        },
    )

    type: str = Field(description="문제 유형 식별자입니다.", examples=["validation_error"])
    title: str = Field(description="사람이 읽을 수 있는 오류 제목입니다.")
    status: int = Field(description="HTTP status code입니다.", examples=[422])
    detail: str = Field(description="사용자 또는 클라이언트에 전달할 오류 설명입니다.")
    instance: str = Field(description="오류가 발생한 요청 경로입니다.", examples=["/auth/login"])
    code: str = Field(description="클라이언트 분기 처리용 오류 코드입니다.")
    request_id: str = Field(description="요청 추적용 request id입니다.", examples=["req_123"])
    errors: list[ProblemErrorItem | dict[str, Any]] = Field(
        default_factory=list,
        description="필드 검증 오류처럼 상세 항목이 필요한 경우 사용합니다.",
    )
