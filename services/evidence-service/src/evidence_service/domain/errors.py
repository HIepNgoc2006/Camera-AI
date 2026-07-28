"""Stable Evidence Storage errors that never echo sensitive input."""

from __future__ import annotations


class EvidenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
