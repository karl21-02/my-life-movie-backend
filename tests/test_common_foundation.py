import json
import logging
import sys

from fastapi import Body
from fastapi.testclient import TestClient

from app.core.errors import AppError
from app.core.logging import JsonLogFormatter
from app.core.config import Settings
from app.main import create_app


def create_test_client() -> TestClient:
    app = create_app()

    @app.get("/test/app-error")
    async def app_error():
        raise AppError(
            status_code=409,
            code="AUTH_CONFLICT",
            title="Auth Conflict",
            detail="Email already exists.",
            type_="auth_conflict",
        )

    @app.get("/test/unhandled")
    async def unhandled_error():
        raise RuntimeError("boom")

    @app.post("/test/validation")
    async def validation_error(email: str = Body(...)):
        return {"email": email}

    return TestClient(app, raise_server_exceptions=False)


def test_health_check_preserves_existing_contract():
    response = create_test_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_id_is_generated_and_returned():
    response = create_test_client().get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"].startswith("req_")


def test_request_id_header_is_reused():
    response = create_test_client().get(
        "/health",
        headers={"X-Request-ID": "req_test"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req_test"


def test_app_error_uses_problem_details_shape():
    response = create_test_client().get(
        "/test/app-error",
        headers={"X-Request-ID": "req_app_error"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "type": "auth_conflict",
        "title": "Auth Conflict",
        "status": 409,
        "detail": "Email already exists.",
        "instance": "/test/app-error",
        "code": "AUTH_CONFLICT",
        "request_id": "req_app_error",
        "errors": [],
    }


def test_validation_error_uses_problem_details_and_redacts_input():
    response = create_test_client().post(
        "/test/validation",
        headers={"X-Request-ID": "req_validation"},
        json={"password": "secret"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["request_id"] == "req_validation"
    assert body["errors"]
    assert "secret" not in response.text


def test_unhandled_exception_uses_problem_details_shape():
    response = create_test_client().get(
        "/test/unhandled",
        headers={"X-Request-ID": "req_unhandled"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_SERVER_ERROR"
    assert body["request_id"] == "req_unhandled"
    assert body["detail"] == "Internal server error."


def test_json_formatter_redacts_sensitive_fields_and_keeps_stack_trace():
    settings = Settings(service_name="svc", environment="test")
    formatter = JsonLogFormatter(settings)

    try:
        raise RuntimeError("sample")
    except RuntimeError:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
        record.event = "external_api_failed"
        record.request_id = "req_log"
        record.token = "secret-token"
        record.password = "secret-password"

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "ERROR"
    assert payload["event"] == "external_api_failed"
    assert payload["request_id"] == "req_log"
    assert payload["exception"]["type"] == "RuntimeError"
    assert "stack_trace" in payload["exception"]
    assert "secret-token" not in json.dumps(payload)
