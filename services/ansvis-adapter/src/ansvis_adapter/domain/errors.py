"""Stable domain errors that never retain rejected event content."""

from __future__ import annotations


class AnsvisAdapterError(ValueError):
    """Carry only a stable error code across adapter boundaries."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
