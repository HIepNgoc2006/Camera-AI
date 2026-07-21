"""Framework-free idempotency values shared with durable receipt adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^idem_(?:source|fallback)_v1_[0-9a-f]{64}$")
CANONICAL_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class IdempotencyIdentityKind(StrEnum):
    SOURCE = "source"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class IdempotencyDescriptor:
    """Opaque identity and fingerprint passed to the future durable inbox."""

    identity_kind: IdempotencyIdentityKind
    idempotency_key: str
    canonical_fingerprint: str
    canonicalization_version: str = "camera_ai_canonical_json_v1"

    def __post_init__(self) -> None:
        if (
            IDEMPOTENCY_KEY_PATTERN.fullmatch(self.idempotency_key) is None
            or CANONICAL_FINGERPRINT_PATTERN.fullmatch(self.canonical_fingerprint) is None
            or self.canonicalization_version != "camera_ai_canonical_json_v1"
        ):
            raise ValueError("invalid idempotency descriptor")
