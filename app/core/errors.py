from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger


logger = get_logger(__name__)


class AppError(Exception):
    """도메인 오류를 공개 API 에러 응답 규격으로 변환하기 위한 공통 예외."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        detail: str,
        title: str | None = None,
        type_: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.title = title or "Application Error"
        self.type = type_ or code.lower()
        self.errors = errors or []
        super().__init__(detail)


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def problem_detail(
    *,
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str,
    type_: str,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "type": type_,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": get_request_id(request),
        "errors": errors or [],
    }


def sanitize_validation_errors(
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sanitized_errors = []
    for error in errors:
        sanitized = {
            key: value
            for key, value in error.items()
            if key not in {"input", "ctx"}
        }
        sanitized_errors.append(sanitized)
    return sanitized_errors


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log_level = "error" if exc.status_code >= 500 else "warning"
    getattr(logger, log_level)(
        exc.detail,
        extra={
            "event": "app_error",
            "request_id": get_request_id(request),
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "error_code": exc.code,
            "error_type": exc.type,
        },
        exc_info=exc.status_code >= 500,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem_detail(
            request=request,
            status=exc.status_code,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            type_=exc.type,
            errors=exc.errors,
        ),
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error occurred."
    logger.warning(
        detail,
        extra={
            "event": "http_error",
            "request_id": get_request_id(request),
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "error_code": "HTTP_ERROR",
            "error_type": "http_error",
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=problem_detail(
            request=request,
            status=exc.status_code,
            code="HTTP_ERROR",
            title="HTTP Error",
            detail=detail,
            type_="http_error",
        ),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = sanitize_validation_errors(exc.errors())
    logger.warning(
        "Request validation failed.",
        extra={
            "event": "validation_error",
            "request_id": get_request_id(request),
            "path": request.url.path,
            "method": request.method,
            "status_code": 422,
            "error_code": "VALIDATION_ERROR",
            "error_type": "validation_error",
        },
    )
    return JSONResponse(
        status_code=422,
        content=problem_detail(
            request=request,
            status=422,
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail="Request validation failed.",
            type_="validation_error",
            errors=errors,
        ),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled server error.",
        extra={
            "event": "unhandled_exception",
            "request_id": get_request_id(request),
            "path": request.url.path,
            "method": request.method,
            "status_code": 500,
            "error_code": "INTERNAL_SERVER_ERROR",
            "error_type": "internal_server_error",
        },
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content=problem_detail(
            request=request,
            status=500,
            code="INTERNAL_SERVER_ERROR",
            title="Internal Server Error",
            detail="Internal server error.",
            type_="internal_server_error",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
