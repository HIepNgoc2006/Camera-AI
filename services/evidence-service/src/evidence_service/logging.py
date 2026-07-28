"""Allowlisted Evidence Storage logging with no media locator or URL fields."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping

_ALLOWED = frozenset(
    {
        "level",
        "service_name",
        "environment",
        "request_id",
        "correlation_id",
        "error_code",
        "outcome",
        "media_kind",
        "state",
        "reconciliation_state",
    }
)


def safe_log(logger: logging.Logger, level: int, fields: Mapping[str, object]) -> None:
    payload = {key: value for key, value in fields.items() if key in _ALLOWED}
    payload.setdefault("service_name", "evidence-storage-service")
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))
