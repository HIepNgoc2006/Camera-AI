"""Framework-free authentication and registered-source policy models."""

from __future__ import annotations

import re
from dataclasses import dataclass

STABLE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
STABLE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


def _require_pattern(value: str, pattern: re.Pattern[str], field: str) -> None:
    if pattern.fullmatch(value) is None:
        raise ValueError(f"{field} must use the approved opaque format")


@dataclass(frozen=True, slots=True)
class RegisteredSource:
    """Authoritative source binding returned by the source registry."""

    subject_ref: str
    source_namespace: str
    tenant_ref: str
    school_ref: str
    active: bool

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise ValueError("active must be a strict boolean")
        _require_pattern(self.subject_ref, STABLE_REF_PATTERN, "subject_ref")
        _require_pattern(self.source_namespace, STABLE_CODE_PATTERN, "source_namespace")
        _require_pattern(self.tenant_ref, STABLE_REF_PATTERN, "tenant_ref")
        _require_pattern(self.school_ref, STABLE_REF_PATTERN, "school_ref")
