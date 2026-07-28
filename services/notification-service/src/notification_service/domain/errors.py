"""Stable notification errors that never carry protected values."""

from __future__ import annotations


class NotificationError(RuntimeError):
    """Domain/application failure represented only by an allowlisted stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"NotificationError(code={self.code!r})"
