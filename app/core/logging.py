import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "api_key",
    "secret",
    "client_secret",
    "payload",
    "prompt",
    "file_content",
    "content",
}

STRUCTURED_FIELDS = (
    "event",
    "request_id",
    "path",
    "method",
    "status_code",
    "duration_ms",
    "error_code",
    "error_type",
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class JsonLogFormatter(logging.Formatter):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "service": self.settings.service_name,
            "environment": self.settings.environment,
            "message": record.getMessage(),
        }

        for field in STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = redact(value)

        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else "Exception",
                "message": str(exc_value),
                "stack_trace": "".join(
                    traceback.format_exception(exc_type, exc_value, exc_traceback)
                ),
            }

        return json.dumps(redact(payload), ensure_ascii=False)


def configure_logging(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(settings))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn.access").disabled = True
    for logger_name in ("openai", "httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
