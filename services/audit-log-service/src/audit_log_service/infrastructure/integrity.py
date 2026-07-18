"""Keyed integrity adapter with injected, non-exportable key material."""

from __future__ import annotations

import hmac
from hashlib import sha256

from audit_log_service.domain.errors import AuditError


class HmacSha256IntegritySigner:
    """HMAC-SHA-256 signer; callers must inject key bytes from an approved provider."""

    __slots__ = ("__key",)

    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise AuditError("AUDIT_INTEGRITY_FAILED")
        self.__key = bytes(key)

    def __repr__(self) -> str:
        return "HmacSha256IntegritySigner(key=<redacted>)"

    def sign(self, message: bytes) -> bytes:
        return hmac.new(self.__key, message, sha256).digest()
