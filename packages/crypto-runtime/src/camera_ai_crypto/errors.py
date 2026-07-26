"""Stable, redacted error contract for the encryption and lookup runtime.

Error codes are the approved database/encryption plan codes. Messages never carry plaintext,
key material, ciphertext, envelope internals or normalized lookup input.
"""

from __future__ import annotations

from enum import StrEnum


class CryptoErrorCode(StrEnum):
    """Stable codes returned to callers; safe for API and log surfaces."""

    KEY_UNAVAILABLE = "ENCRYPTION_KEY_UNAVAILABLE"
    ENVELOPE_INVALID = "ENCRYPTION_ENVELOPE_INVALID"
    AUTH_FAILED = "ENCRYPTION_AUTH_FAILED"
    LOOKUP_NORMALIZATION_INVALID = "LOOKUP_NORMALIZATION_INVALID"


class CryptoError(Exception):
    """Base failure carrying only a stable code and a fixed redacted message."""

    code: CryptoErrorCode

    def __init__(self, code: CryptoErrorCode) -> None:
        super().__init__(str(code))
        self.code = code

    def __str__(self) -> str:
        return str(self.code)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!s})"


class KeyUnavailableError(CryptoError):
    """Key provider is unwired, the key is unknown, disabled, or not readable."""

    def __init__(self) -> None:
        super().__init__(CryptoErrorCode.KEY_UNAVAILABLE)


class EnvelopeInvalidError(CryptoError):
    """Envelope failed the strict size, version, or structure allowlist."""

    def __init__(self) -> None:
        super().__init__(CryptoErrorCode.ENVELOPE_INVALID)


class AuthFailedError(CryptoError):
    """AEAD authentication failed: tampered ciphertext, header, or mismatched AAD."""

    def __init__(self) -> None:
        super().__init__(CryptoErrorCode.AUTH_FAILED)


class LookupNormalizationError(CryptoError):
    """Lookup input is invalid or ambiguous for the requested normalization version."""

    def __init__(self) -> None:
        super().__init__(CryptoErrorCode.LOOKUP_NORMALIZATION_INVALID)
