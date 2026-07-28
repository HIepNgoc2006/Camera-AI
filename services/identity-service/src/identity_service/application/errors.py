"""Stable application errors mapped by the API boundary."""

from __future__ import annotations


class AuthenticationError(RuntimeError):
    def __init__(self, code: str, *, retry_after: int | None = None) -> None:
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)
