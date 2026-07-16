"""Request-correlation identifier policy."""

from __future__ import annotations

import re
from collections.abc import Sequence
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 64
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def generated_request_id() -> str:
    return f"req_{uuid4().hex}"


def select_request_id(values: Sequence[str]) -> str:
    if len(values) != 1:
        return generated_request_id()
    candidate = values[0]
    if len(candidate) > MAX_REQUEST_ID_LENGTH or REQUEST_ID_PATTERN.fullmatch(candidate) is None:
        return generated_request_id()
    return candidate
