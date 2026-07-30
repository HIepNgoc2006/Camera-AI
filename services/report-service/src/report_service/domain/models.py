"""Immutable report and export domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from report_service.domain.errors import ReportError

_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
_UPPER_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
_CORRELATION_ID = re.compile(r"^cor_[A-Za-z0-9_-]{8,120}$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")


def _require(condition: bool) -> None:
    if not condition:
        raise ReportError("REPORT_REQUEST_INVALID")


def _aware(value: datetime) -> None:
    _require(value.tzinfo is not None and value.utcoffset() is not None)


def _uuid(value: UUID | None) -> None:
    if value is not None:
        _require(value.int != 0)


class ConsentState(StrEnum):
    ALLOWED = "allowed"
    NOT_REQUIRED = "not_required"
    BLOCKED = "blocked"


class ExportState(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    AVAILABLE = "available"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestContext:
    actor_id: UUID
    tenant_id: UUID
    authorized_school_ids: frozenset[UUID]
    authorized_class_ids: frozenset[UUID]
    permission_codes: frozenset[str]
    request_id: str
    correlation_id: str
    purpose_code: str
    authenticated: bool

    def __post_init__(self) -> None:
        _uuid(self.actor_id)
        _uuid(self.tenant_id)
        _require(1 <= len(self.authorized_school_ids) <= 100)
        _require(len(self.authorized_class_ids) <= 1_000)
        for value in self.authorized_school_ids | self.authorized_class_ids:
            _uuid(value)
        _require(_REQUEST_ID.fullmatch(self.request_id) is not None)
        _require(_CORRELATION_ID.fullmatch(self.correlation_id) is not None)
        _require(_CODE.fullmatch(self.purpose_code) is not None)
        _require(len(self.permission_codes) <= 256)
        for permission in self.permission_codes:
            _require(_CODE.fullmatch(permission) is not None)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportQuery:
    report_type: str
    school_ids: frozenset[UUID]
    class_ids: frozenset[UUID]
    period_start: datetime
    period_end: datetime

    def __post_init__(self) -> None:
        _require(_CODE.fullmatch(self.report_type) is not None)
        _require(1 <= len(self.school_ids) <= 100 and len(self.class_ids) <= 1_000)
        for value in self.school_ids | self.class_ids:
            _uuid(value)
        _aware(self.period_start)
        _aware(self.period_end)
        _require(self.period_start < self.period_end)

    @property
    def cross_scope(self) -> bool:
        return len(self.school_ids) > 1 or len(self.class_ids) > 1


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportRow:
    school_id: UUID
    class_id: UUID | None
    category_code: str
    occurred_at: datetime
    consent_state: ConsentState
    retention_until: datetime
    legal_hold_active: bool

    def __post_init__(self) -> None:
        _uuid(self.school_id)
        _uuid(self.class_id)
        _require(_CODE.fullmatch(self.category_code) is not None)
        _aware(self.occurred_at)
        _aware(self.retention_until)


@dataclass(frozen=True, slots=True)
class AggregateCell:
    category_code: str
    count: int | None
    sample_count: int
    suppressed: bool
    policy_version: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportCommand:
    query: ReportQuery
    reason_code: str
    approval_status: str
    format_code: str
    idempotency_key: str

    def __post_init__(self) -> None:
        _require(_UPPER_CODE.fullmatch(self.reason_code) is not None)
        _require(self.approval_status in {"not_required", "approved", "denied"})
        _require(self.format_code in {"csv", "json"})
        _require(_IDEMPOTENCY.fullmatch(self.idempotency_key) is not None)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportJob:
    export_id: UUID
    actor_id: UUID
    tenant_id: UUID
    query: ReportQuery
    reason_code: str
    format_code: str
    state: ExportState
    created_at: datetime
    expires_at: datetime
    row_count: int | None = None
    artifact_ref: UUID | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.export_id)
        _uuid(self.actor_id)
        _uuid(self.tenant_id)
        _uuid(self.artifact_ref)
        _aware(self.created_at)
        _aware(self.expires_at)
        _require(self.expires_at > self.created_at)
        _require((self.state is ExportState.AVAILABLE) == (self.artifact_ref is not None))
        if self.row_count is not None:
            _require(0 <= self.row_count <= 10_000_000)


@dataclass(frozen=True, slots=True)
class DownloadGrant:
    export_id: UUID
    expires_at: datetime
    signed_url: str

    def __repr__(self) -> str:
        return (
            f"DownloadGrant(export_id={self.export_id!r}, "
            f"expires_at={self.expires_at!r}, signed_url=<redacted>)"
        )
