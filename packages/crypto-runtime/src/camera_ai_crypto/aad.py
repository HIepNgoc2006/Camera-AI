"""`aad_schema=v1` additional-authenticated-data binding.

The AAD binds a ciphertext to immutable coordinates: service, `schema.table.field`, record UUID,
tenant scope and envelope version. Changing any bound coordinate must make authentication fail.
Mutable business fields are never bound, and no sensitive plaintext enters the AAD.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

AAD_SCHEMA_V1 = 1
_AAD_PREFIX = "camera-ai|ENCV1|v1"
_SERVICE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_FIELD_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}\.[a-z][a-z0-9_]{0,62}\.[a-z][a-z0-9_]{0,62}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class FieldBinding:
    """Immutable coordinates of one encrypted field value."""

    service: str
    field_path: str
    record_id: UUID
    tenant_ref: str

    def __post_init__(self) -> None:
        if _SERVICE_PATTERN.fullmatch(self.service) is None:
            raise ValueError("invalid service reference")
        if _FIELD_PATTERN.fullmatch(self.field_path) is None:
            raise ValueError("invalid field path")
        if _TENANT_PATTERN.fullmatch(self.tenant_ref) is None:
            raise ValueError("invalid tenant reference")

    def to_aad(self) -> bytes:
        """Return the canonical AAD byte string for this binding."""

        parts = (
            _AAD_PREFIX,
            self.service,
            self.field_path,
            str(self.record_id),
            self.tenant_ref,
        )
        return "|".join(parts).encode("utf-8")
