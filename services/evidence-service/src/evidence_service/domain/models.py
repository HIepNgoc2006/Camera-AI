"""Immutable Evidence Storage domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from evidence_service.domain.errors import EvidenceError

_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
_REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
_CORRELATION_ID = re.compile(r"^cor_[A-Za-z0-9_-]{8,120}$")
_OBJECT_KEY = re.compile(r"^evidence/v1/[0-9a-f]{2}/[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_KEY_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def _require(condition: bool, code: str = "EVIDENCE_REQUEST_INVALID") -> None:
    if not condition:
        raise EvidenceError(code)


def _aware(value: datetime) -> None:
    _require(value.tzinfo is not None and value.utcoffset() is not None)


def _uuid(value: UUID | None) -> None:
    if value is not None:
        _require(value.int != 0)


def _code(value: str) -> None:
    _require(_CODE.fullmatch(value) is not None)


class EvidenceState(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    QUARANTINED = "quarantined"
    AVAILABLE = "available"
    DELETE_PENDING = "delete_pending"
    DELETED = "deleted"
    MISSING = "missing"
    FAILED = "failed"


class ScanState(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class AccessAction(StrEnum):
    VIEW_METADATA = "view_metadata"
    VIEW_THUMBNAIL = "view_thumbnail"
    VIEW_ORIGINAL = "view_original"
    DOWNLOAD = "download"
    EXPORT = "export"


class ConsentState(StrEnum):
    ALLOWED = "allowed"
    NOT_REQUIRED = "not_required"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class LegalHoldState(StrEnum):
    NONE = "none"
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceObject:
    evidence_id: UUID
    tenant_id: UUID
    school_id: UUID
    source_event_id: UUID
    camera_id: UUID | None
    task_id: UUID | None
    captured_at: datetime
    received_at: datetime
    object_key_ciphertext: bytes
    bucket_ref: str
    provider_version_ciphertext: bytes | None
    encryption_key_version_ref: str
    media_kind: MediaKind
    content_type: str
    original_extension: str
    size_bytes: int
    sha256: str | None
    width: int | None
    height: int | None
    duration_ms: int | None
    sensitivity: str
    purpose_code: str
    state: EvidenceState
    scan_state: ScanState
    retention_policy_version: str
    retention_days: int
    retention_expires_at: datetime
    legal_hold_state: LegalHoldState
    created_actor_id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    deletion_reason_code: str | None
    deletion_job_ref: UUID | None
    deletion_request_id: str | None
    deletion_correlation_id: str | None
    row_version: int

    def __post_init__(self) -> None:
        for uuid_value in (
            self.evidence_id,
            self.tenant_id,
            self.school_id,
            self.source_event_id,
            self.camera_id,
            self.task_id,
            self.created_actor_id,
            self.deletion_job_ref,
        ):
            _uuid(uuid_value)
        for code_value in (
            self.bucket_ref,
            self.sensitivity,
            self.purpose_code,
            self.retention_policy_version,
        ):
            _code(code_value)
        _require(self.content_type in {"image/jpeg", "image/png", "image/webp", "video/mp4"})
        _require(_KEY_VERSION.fullmatch(self.encryption_key_version_ref) is not None)
        _require(self.original_extension in {"jpg", "jpeg", "png", "webp", "mp4"})
        _require(0 <= self.size_bytes <= 250 * 1024 * 1024)
        if self.sha256 is not None:
            _require(_SHA256.fullmatch(self.sha256) is not None)
        _require((self.width is None) == (self.height is None))
        if self.width is not None and self.height is not None:
            _require(1 <= self.width <= 32_768 and 1 <= self.height <= 32_768)
        if self.media_kind is MediaKind.IMAGE:
            _require(self.duration_ms is None)
        elif self.duration_ms is not None:
            _require(1 <= self.duration_ms <= 86_400_000)
        _require(self.sensitivity in {"high", "critical"})
        _require(self.retention_days in {15, 30, 180, 365})
        _aware(self.retention_expires_at)
        _aware(self.captured_at)
        _aware(self.received_at)
        _aware(self.created_at)
        _aware(self.updated_at)
        if self.deleted_at is not None:
            _aware(self.deleted_at)
        if self.deletion_reason_code is not None:
            _require(_REASON_CODE.fullmatch(self.deletion_reason_code) is not None)
        if self.deletion_request_id is not None:
            _require(_REQUEST_ID.fullmatch(self.deletion_request_id) is not None)
        if self.deletion_correlation_id is not None:
            _require(_CORRELATION_ID.fullmatch(self.deletion_correlation_id) is not None)
        deletion_values = (
            self.deletion_reason_code,
            self.deletion_job_ref,
            self.deletion_request_id,
            self.deletion_correlation_id,
        )
        _require(
            all(value is None for value in deletion_values)
            or all(value is not None for value in deletion_values)
        )
        _require((self.state is EvidenceState.DELETED) == (self.deleted_at is not None))
        _require(self.captured_at <= self.received_at <= self.created_at)
        _require(self.retention_expires_at > self.created_at)
        _require(self.updated_at >= self.created_at and self.row_version >= 1)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceLink:
    link_id: UUID
    evidence_id: UUID
    tenant_id: UUID
    school_id: UUID
    resource_type: str
    resource_id: UUID
    link_purpose: str
    sequence_role: str
    sequence_index: int
    selection_policy_version: str
    linked_at: datetime

    def __post_init__(self) -> None:
        for uuid_value in (
            self.link_id,
            self.evidence_id,
            self.tenant_id,
            self.school_id,
            self.resource_id,
        ):
            _uuid(uuid_value)
        for code_value in (
            self.resource_type,
            self.link_purpose,
            self.sequence_role,
            self.selection_policy_version,
        ):
            _code(code_value)
        _require(0 <= self.sequence_index <= 99)
        _aware(self.linked_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestContext:
    actor_id: UUID
    tenant_id: UUID
    school_id: UUID
    request_id: str
    correlation_id: str
    purpose_code: str
    actor_authenticated: bool
    actor_permission_codes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for value in (self.actor_id, self.tenant_id, self.school_id):
            _uuid(value)
        _require(_REQUEST_ID.fullmatch(self.request_id) is not None)
        _require(_CORRELATION_ID.fullmatch(self.correlation_id) is not None)
        _code(self.purpose_code)
        _require(len(self.actor_permission_codes) <= 256)
        for permission in self.actor_permission_codes:
            _code(permission)


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadCommand:
    source_event_id: UUID
    camera_id: UUID | None
    task_id: UUID | None
    captured_at: datetime
    media_kind: MediaKind
    content_type: str
    original_extension: str
    declared_size_bytes: int
    sensitivity: str
    retention_policy_version: str
    retention_days: int
    retention_expires_at: datetime

    def __post_init__(self) -> None:
        for value in (self.source_event_id, self.camera_id, self.task_id):
            _uuid(value)
        _require(self.content_type in {"image/jpeg", "image/png", "image/webp", "video/mp4"})
        _require(
            self.original_extension.casefold().lstrip(".") in {"jpg", "jpeg", "png", "webp", "mp4"}
        )
        _require(1 <= self.declared_size_bytes <= 250 * 1024 * 1024)
        _require(self.sensitivity in {"high", "critical"})
        _require(self.retention_days in {15, 30, 180, 365})
        _code(self.retention_policy_version)
        _aware(self.captured_at)
        _aware(self.retention_expires_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredObjectFacts:
    object_key: str
    provider_version: str
    size_bytes: int
    sha256: str
    content_type: str
    header: bytes
    width: int | None
    height: int | None
    duration_ms: int | None

    def __post_init__(self) -> None:
        _require(_OBJECT_KEY.fullmatch(self.object_key) is not None)
        _require(1 <= len(self.provider_version) <= 512)
        _require(1 <= self.size_bytes <= 250 * 1024 * 1024)
        _require(_SHA256.fullmatch(self.sha256) is not None)
        _require(self.content_type in {"image/jpeg", "image/png", "image/webp", "video/mp4"})
        _require(12 <= len(self.header) <= 65_536)
        _require((self.width is None) == (self.height is None))
        if self.width is not None and self.height is not None:
            _require(1 <= self.width <= 32_768 and 1 <= self.height <= 32_768)
        if self.duration_ms is not None:
            _require(1 <= self.duration_ms <= 86_400_000)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessRequest:
    evidence_id: UUID
    action: AccessAction
    ttl_seconds: int | None
    consent_state: ConsentState
    reason_code: str | None = None
    approval_status: str = "not_required"
    recipient_control_code: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.evidence_id)
        if self.ttl_seconds is not None:
            _require(1 <= self.ttl_seconds <= 300)
        if self.reason_code is not None:
            _require(_REASON_CODE.fullmatch(self.reason_code) is not None)
        _code(self.approval_status)
        if self.recipient_control_code is not None:
            _code(self.recipient_control_code)


@dataclass(frozen=True, slots=True)
class UploadTicket:
    evidence_id: UUID
    expires_at: datetime
    upload_url: str
    upload_fields: tuple[tuple[str, str], ...]

    def __repr__(self) -> str:
        return (
            "UploadTicket("
            f"evidence_id={self.evidence_id!r}, expires_at={self.expires_at!r}, "
            "upload_url=<redacted>, upload_fields=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class AccessGrant:
    evidence_id: UUID
    action: AccessAction
    expires_at: datetime
    signed_url: str | None

    def __repr__(self) -> str:
        return (
            "AccessGrant("
            f"evidence_id={self.evidence_id!r}, action={self.action!r}, "
            f"expires_at={self.expires_at!r}, signed_url=<redacted>)"
        )
