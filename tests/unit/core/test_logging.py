import json
import logging
import sys

import pytest

from app.core.config import Settings
from app.core.logging import JsonLogFormatter


pytestmark = pytest.mark.unit


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
