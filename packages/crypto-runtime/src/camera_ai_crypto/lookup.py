"""`LOOKUP-V1` exact-match lookup values.

Ciphertext is never searched or indexed. Approved exact lookups use a full-length HMAC-SHA-256
under a lookup key that is separate from any encryption or wrapping key, with mandatory domain
separation per service/table/field/purpose and normalization version. The digest serves approved
exact lookup and dedup only; it is never returned through an API or written to a log.
"""

from __future__ import annotations

import hmac
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from .errors import LookupNormalizationError

LOOKUP_KEY_MIN_LENGTH = 32
_LOOKUP_PREFIX = "camera-ai|LOOKUP-V1"
_DOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s.]{1,63}(?:\.[^@\s.]{1,63})+$")
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_MAX_INPUT_LENGTH = 512


class NormalizationVersion(StrEnum):
    """Approved canonicalization rules; one lookup value uses exactly one of them."""

    EMAIL_V1 = "email-v1"
    CONTACT_PHONE_V1 = "contact-phone-v1"
    CONTACT_EMAIL_V1 = "contact-email-v1"
    DEVICE_TOKEN_V1 = "device-token-v1"


def _normalize_email(value: str) -> str:
    candidate = unicodedata.normalize("NFC", value).strip().casefold()
    if _EMAIL_PATTERN.fullmatch(candidate) is None:
        raise LookupNormalizationError
    return candidate


def _normalize_phone(value: str) -> str:
    candidate = unicodedata.normalize("NFC", value).strip()
    compact = re.sub(r"[\s()\-.]", "", candidate)
    if _E164_PATTERN.fullmatch(compact) is None:
        raise LookupNormalizationError
    return compact


def canonicalize(value: str | bytes, version: NormalizationVersion) -> bytes:
    """Return canonical bytes for one lookup input, or fail closed.

    A rejected input is never retried silently under a different normalization.
    """

    if version is NormalizationVersion.DEVICE_TOKEN_V1:
        if not isinstance(value, bytes) or not 1 <= len(value) <= _MAX_INPUT_LENGTH:
            raise LookupNormalizationError
        return value

    if not isinstance(value, str) or not 1 <= len(value) <= _MAX_INPUT_LENGTH:
        raise LookupNormalizationError

    match version:
        case NormalizationVersion.EMAIL_V1:
            return _normalize_email(value).encode("utf-8")
        case NormalizationVersion.CONTACT_EMAIL_V1:
            return b"email:" + _normalize_email(value).encode("utf-8")
        case NormalizationVersion.CONTACT_PHONE_V1:
            return b"phone:" + _normalize_phone(value).encode("utf-8")


@dataclass(frozen=True, slots=True)
class LookupDomain:
    """Domain separation for one approved lookup purpose."""

    name: str
    tenant_ref: str
    version: NormalizationVersion

    def __post_init__(self) -> None:
        if (
            _DOMAIN_PATTERN.fullmatch(self.name) is None
            or _TENANT_PATTERN.fullmatch(self.tenant_ref) is None
        ):
            raise LookupNormalizationError

    def prefix(self) -> bytes:
        """Return the canonical domain-separation prefix."""

        parts = (_LOOKUP_PREFIX, self.name, str(self.version), self.tenant_ref, "")
        return "|".join(parts).encode("utf-8")


@dataclass(frozen=True, slots=True)
class LookupHasher:
    """Computes LOOKUP-V1 digests under a dedicated lookup key."""

    lookup_key: bytes

    def __post_init__(self) -> None:
        if len(self.lookup_key) < LOOKUP_KEY_MIN_LENGTH:
            raise LookupNormalizationError

    def digest(self, value: str | bytes, domain: LookupDomain) -> bytes:
        """Return the full-length HMAC digest for an approved exact lookup."""

        canonical = canonicalize(value, domain.version)
        return hmac.new(self.lookup_key, domain.prefix() + canonical, sha256).digest()

    def matches(self, value: str | bytes, domain: LookupDomain, stored: bytes) -> bool:
        """Compare a candidate against a stored digest in constant time."""

        return hmac.compare_digest(self.digest(value, domain), stored)
