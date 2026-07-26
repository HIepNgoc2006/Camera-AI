"""Allowlist structured logging for the drain worker.

Only fixed metadata and non-negative counters are serialized; free-form record content, broker
URLs, payloads and identifiers never reach the log stream.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

SERVICE_NAME = "event-outbox-worker"
_COUNTER_FIELDS = ("claimed", "published", "retry_scheduled", "dead_lettered")


class WorkerJsonLogFormatter(logging.Formatter):
    """Serialize fixed fields plus allowlisted integer counters."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str | int] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service_name": SERVICE_NAME,
            "environment": _text(record, "environment"),
            "event": _text(record, "event"),
        }
        for name in ("error_code",):
            value: object = getattr(record, name, None)
            if isinstance(value, str):
                payload[name] = value
        for name in _COUNTER_FIELDS:
            counter: object = getattr(record, name, None)
            if isinstance(counter, int) and counter >= 0:
                payload[name] = counter
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(level: str, environment: str) -> logging.Logger:
    """Return the worker logger with the allowlist formatter attached exactly once."""

    logger = logging.getLogger(SERVICE_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(WorkerJsonLogFormatter())
        logger.addHandler(handler)
    logger = logging.LoggerAdapter(logger, {"environment": environment}).logger
    return logger


def _text(record: logging.LogRecord, name: str) -> str:
    value: object = getattr(record, name, "unspecified")
    return value if isinstance(value, str) else "unspecified"
