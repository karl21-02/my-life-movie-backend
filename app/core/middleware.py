import time
from uuid import uuid4

from fastapi import Request, Response

from app.core.logging import get_logger


logger = get_logger(__name__)
REQUEST_ID_HEADER = "X-Request-ID"


async def request_context_middleware(request: Request, call_next) -> Response:
    """요청마다 request id를 붙이고 구조화된 접근 로그를 남긴다."""

    request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid4().hex}"
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(
            "request_failed",
            extra={
                "event": "request_failed",
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": 500,
                "duration_ms": duration_ms,
            },
            exc_info=True,
        )
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers[REQUEST_ID_HEADER] = request_id

    status_code = response.status_code
    if status_code >= 500:
        log = logger.error
    elif status_code >= 400:
        log = logger.warning
    else:
        log = logger.info

    log(
        "request_completed",
        extra={
            "event": "request_completed",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
