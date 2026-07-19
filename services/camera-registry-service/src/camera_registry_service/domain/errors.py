"""Stable redacted Camera Registry errors."""

from __future__ import annotations


class CameraRegistryError(Exception):
    """An error that exposes only a stable code, never rejected input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
