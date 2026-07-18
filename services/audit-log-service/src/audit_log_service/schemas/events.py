"""Strict versioned publisher DTOs with redacted parse failures."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from ipaddress import IPv4Network, IPv6Network
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyNetwork,
    ValidationError,
    field_validator,
    model_validator,
)

from audit_log_service.domain.errors import AuditError
from audit_log_service.domain.models import AuditChanges, AuditResult

STABLE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
SOURCE_SERVICE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
ACTION_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")
REASON_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
REQUEST_PATTERN = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
CORRELATION_PATTERN = re.compile(r"^cor_[A-Za-z0-9_-]{8,120}$")
MAX_CHANGE_ITEMS = 32
MAX_CHANGE_BYTES = 16_384


def _stable_code(value: str) -> str:
    if STABLE_CODE_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a stable code")
    return value


StableCode = Annotated[str, AfterValidator(_stable_code)]
Count = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]


class StrictAuditModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuditChangesV1(StrictAuditModel):
    """Controlled summary; values can only be stable codes, UUIDs, booleans, or counts."""

    schema_version: Literal["audit_changes_v1"]
    changed_fields: tuple[StableCode, ...] = Field(default=(), max_length=MAX_CHANGE_ITEMS)
    state_before_codes: dict[StableCode, StableCode | bool] = Field(default_factory=dict)
    state_after_codes: dict[StableCode, StableCode | bool] = Field(default_factory=dict)
    reference_ids: dict[StableCode, UUID] = Field(default_factory=dict)
    count_summary: dict[StableCode, Count] = Field(default_factory=dict)
    policy_versions: dict[StableCode, StableCode] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        mappings = (
            self.state_before_codes,
            self.state_after_codes,
            self.reference_ids,
            self.count_summary,
            self.policy_versions,
        )
        if any(len(mapping) > MAX_CHANGE_ITEMS for mapping in mappings):
            raise ValueError("audit change map exceeds its item limit")
        if len(set(self.changed_fields)) != len(self.changed_fields):
            raise ValueError("audit changed fields must be unique")
        if not any((self.changed_fields, *mappings)):
            raise ValueError("audit changes cannot contain only a schema version")
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        if len(encoded) > MAX_CHANGE_BYTES:
            raise ValueError("audit changes exceed the size limit")
        return self

    def to_domain(self) -> AuditChanges:
        return AuditChanges(
            changed_fields=tuple(self.changed_fields),
            state_before_codes=tuple(sorted(self.state_before_codes.items())),
            state_after_codes=tuple(sorted(self.state_after_codes.items())),
            reference_ids=tuple(sorted(self.reference_ids.items())),
            count_summary=tuple(sorted(self.count_summary.items())),
            policy_versions=tuple(sorted(self.policy_versions.items())),
        )


class AuditEventV1(StrictAuditModel):
    """Publisher-controlled portion of the AuditEventV1 envelope."""

    event_schema_version: Literal[1]
    source_service: str = Field(min_length=3, max_length=64)
    source_event_id: UUID
    correlation_id: str | None = Field(default=None, min_length=12, max_length=124)
    action: str = Field(min_length=3, max_length=96)
    purpose_code: StableCode | None = None
    resource_type: StableCode
    resource_id: UUID | None = None
    resource_ref: StableCode | None = None
    request_id: str = Field(min_length=12, max_length=124)
    result: AuditResult
    reason_code: str | None = Field(default=None, min_length=2, max_length=64)
    occurred_at: datetime
    ip_prefix: IPvAnyNetwork | None = None
    user_agent_family: StableCode | None = None
    changes: AuditChangesV1 | None = None

    @field_validator("source_service")
    @classmethod
    def validate_source_service(cls, value: str) -> str:
        if SOURCE_SERVICE_PATTERN.fullmatch(value) is None:
            raise ValueError("source service must be a stable service code")
        return value

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if ACTION_PATTERN.fullmatch(value) is None:
            raise ValueError("action must be an uppercase stable code")
        return value

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        if REQUEST_PATTERN.fullmatch(value) is None:
            raise ValueError("request id must use the approved opaque format")
        return value

    @field_validator("correlation_id")
    @classmethod
    def validate_correlation_id(cls, value: str | None) -> str | None:
        if value is not None and CORRELATION_PATTERN.fullmatch(value) is None:
            raise ValueError("correlation id must use the approved opaque format")
        return value

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str | None) -> str | None:
        if value is not None and REASON_PATTERN.fullmatch(value) is None:
            raise ValueError("reason code must be an uppercase stable code")
        return value

    @field_validator("changes", mode="before")
    @classmethod
    def normalize_empty_changes(cls, value: object) -> object:
        return None if value == {} else value

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        for value in (self.source_event_id, self.resource_id):
            if value is not None and value.int == 0:
                raise ValueError("opaque identifiers must be non-zero")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        if self.resource_id is not None and self.resource_ref is not None:
            raise ValueError("resource_id and resource_ref are mutually exclusive")
        if self.result in {AuditResult.DENIED, AuditResult.FAILED} and self.reason_code is None:
            raise ValueError("denied and failed events require a reason code")
        if self.ip_prefix is not None:
            limit = 24 if self.ip_prefix.version == 4 else 48
            if self.ip_prefix.prefixlen > limit:
                raise ValueError("ip_prefix is more precise than the approved privacy boundary")
        return self

    def network(self) -> IPv4Network | IPv6Network | None:
        if self.ip_prefix is None:
            return None
        if isinstance(self.ip_prefix, (IPv4Network, IPv6Network)):
            return self.ip_prefix
        raise AuditError("AUDIT_EVENT_INVALID")


def parse_audit_event(value: Mapping[str, object]) -> AuditEventV1:
    """Parse without allowing Pydantic to expose a rejected value through service errors."""

    try:
        return AuditEventV1.model_validate(value)
    except ValidationError:
        raise AuditError("AUDIT_EVENT_INVALID") from None
