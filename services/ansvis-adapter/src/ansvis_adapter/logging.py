"""Structured allowlist logging for a high-sensitivity ingestion boundary."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from ansvis_adapter.config import Settings

SERVICE_NAME = "ansvis-adapter"


def _text_attribute(record: logging.LogRecord, name: str, default: str) -> str:
    value: object = getattr(record, name, default)
    return value if isinstance(value, str) else default


class JsonLogFormatter(logging.Formatter):
    """Serialize fixed metadata fields and ignore free-form record content."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str | int] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service_name": SERVICE_NAME,
            "environment": _text_attribute(record, "environment", "unknown"),
            "event": _text_attribute(record, "event", "unspecified"),
            "request_id": _text_attribute(record, "request_id", "unavailable"),
        }
        status_code: object = getattr(record, "status_code", None)
        if isinstance(status_code, int):
            payload["status_code"] = status_code
        for name in ("error_code", "exception_type"):
            value: object = getattr(record, name, None)
            if isinstance(value, str):
                payload[name] = value
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(settings: Settings) -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger(SERVICE_NAME)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
    return logger


def log_request(
    logger: logging.Logger,
    *,
    environment: str,
    event: str,
    request_id: str,
    status_code: int,
    error_code: str | None = None,
    exception_type: str | None = None,
) -> None:
    extra: dict[str, str | int] = {
        "environment": environment,
        "event": event,
        "request_id": request_id,
        "status_code": status_code,
    }
    if error_code is not None:
        extra["error_code"] = error_code
    if exception_type is not None:
        extra["exception_type"] = exception_type
    logger.log(
        logging.ERROR if status_code >= 500 else logging.INFO, "structured_event", extra=extra
    )
