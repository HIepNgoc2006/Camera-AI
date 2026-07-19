"""Framework-free Camera Registry entities, commands, and policies."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Never
from uuid import UUID

from camera_registry_service.domain.errors import CameraRegistryError

STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
UPPER_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
IDEMPOTENCY_KEY = re.compile(r"^idem_[A-Za-z0-9_-]{8,120}$")
SECRET_REFERENCE = re.compile(r"^sec_v1_[A-Za-z0-9_-]{32,96}$")

AUDIT_ACTION = "CAMERA_MAPPING_CHANGED"
AUDIT_PURPOSE_CODE = "camera_operations"

CAMERA_PURPOSE_CODES = frozenset(
    {
        "emotion_insight",
        "kitchen_ppe",
        "littering_detection",
        "staff_timekeeping",
        "student_attendance",
        "student_uniform",
        "suspected_smoking",
    }
)


class ZoneType(StrEnum):
    GATE = "gate"
    YARD = "yard"
    HALLWAY = "hallway"
    KITCHEN = "kitchen"
    OTHER = "other"


ZONE_PURPOSE_COMPATIBILITY: dict[ZoneType, frozenset[str]] = {
    ZoneType.GATE: frozenset(
        {
            "emotion_insight",
            "littering_detection",
            "staff_timekeeping",
            "student_attendance",
            "student_uniform",
            "suspected_smoking",
        }
    ),
    ZoneType.YARD: frozenset({"littering_detection", "student_uniform", "suspected_smoking"}),
    ZoneType.HALLWAY: frozenset(
        {
            "emotion_insight",
            "littering_detection",
            "staff_timekeeping",
            "student_attendance",
            "student_uniform",
            "suspected_smoking",
        }
    ),
    ZoneType.KITCHEN: frozenset({"kitchen_ppe"}),
    ZoneType.OTHER: frozenset({"littering_detection", "suspected_smoking"}),
}


class ZoneSensitivity(StrEnum):
    HIGH = "high"
    CRITICAL = "critical"


class ZoneStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CameraStatus(StrEnum):
    PENDING = "pending"
    ONLINE = "online"
    OFFLINE = "offline"
    DISABLED = "disabled"


class ZoneChangeOperation(StrEnum):
    UPDATE = "zone_updated"
    DEACTIVATE = "zone_deactivated"


class CameraChangeOperation(StrEnum):
    UPDATE = "camera_updated"
    MAP = "camera_mapped"
    DEACTIVATE = "camera_deactivated"


def _fail() -> Never:
    raise CameraRegistryError("CAMERA_INPUT_INVALID")


def _nonzero(value: UUID | None) -> None:
    if value is not None and value.int == 0:
        _fail()


def _aware(value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        _fail()


def _matches(value: str | None, pattern: re.Pattern[str]) -> None:
    if value is not None and pattern.fullmatch(value) is None:
        _fail()


def _purpose_tuple(value: tuple[str, ...]) -> None:
    if not value or len(value) > len(CAMERA_PURPOSE_CODES) or len(set(value)) != len(value):
        _fail()
    if not set(value).issubset(CAMERA_PURPOSE_CODES):
        _fail()


def _zone_purpose_tuple(zone_type: ZoneType, value: tuple[str, ...]) -> None:
    _purpose_tuple(value)
    if not set(value).issubset(ZONE_PURPOSE_COMPATIBILITY[zone_type]):
        raise CameraRegistryError("CAMERA_PURPOSE_DENIED")


@dataclass(frozen=True, slots=True)
class Zone:
    zone_id: UUID
    school_id: UUID
    code: str
    name: str
    zone_type: ZoneType
    sensitivity: ZoneSensitivity
    purpose_codes: tuple[str, ...]
    status: ZoneStatus
    deactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    row_version: int

    def __post_init__(self) -> None:
        _nonzero(self.zone_id)
        _nonzero(self.school_id)
        _matches(self.code, STABLE_CODE)
        _zone_purpose_tuple(self.zone_type, self.purpose_codes)
        _aware(self.deactivated_at)
        _aware(self.created_at)
        _aware(self.updated_at)
        if not self.name or len(self.name) > 128 or self.row_version < 1:
            _fail()
        if (self.status is ZoneStatus.INACTIVE) != (self.deactivated_at is not None):
            _fail()
        if self.updated_at < self.created_at:
            _fail()


@dataclass(frozen=True, slots=True)
class Camera:
    camera_id: UUID
    school_id: UUID
    zone_id: UUID
    code: str
    display_name: str
    purpose_codes: tuple[str, ...]
    source_id: UUID | None
    task_id: UUID | None
    mapping_purpose_code: str | None
    credential_ref: str | None
    schedule_version: str | None
    config_version: str
    status: CameraStatus
    last_seen_at: datetime | None
    deactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    row_version: int

    def __post_init__(self) -> None:
        for identifier in (self.camera_id, self.school_id, self.zone_id):
            _nonzero(identifier)
        _nonzero(self.source_id)
        _nonzero(self.task_id)
        _matches(self.code, STABLE_CODE)
        _purpose_tuple(self.purpose_codes)
        _matches(self.mapping_purpose_code, STABLE_CODE)
        _matches(self.credential_ref, SECRET_REFERENCE)
        _matches(self.schedule_version, STABLE_CODE)
        _matches(self.config_version, STABLE_CODE)
        for instant in (
            self.last_seen_at,
            self.deactivated_at,
            self.created_at,
            self.updated_at,
        ):
            _aware(instant)
        if not self.display_name or len(self.display_name) > 128 or self.row_version < 1:
            _fail()
        mapping_values = (
            self.source_id,
            self.task_id,
            self.mapping_purpose_code,
            self.schedule_version,
        )
        if any(value is None for value in mapping_values) != all(
            value is None for value in mapping_values
        ):
            _fail()
        if (
            self.mapping_purpose_code is not None
            and self.mapping_purpose_code not in self.purpose_codes
        ):
            raise CameraRegistryError("CAMERA_PURPOSE_DENIED")
        if (self.status is CameraStatus.DISABLED) != (self.deactivated_at is not None):
            _fail()
        if self.updated_at < self.created_at:
            _fail()


@dataclass(frozen=True, slots=True)
class TrustedRegistryContext:
    school_id: UUID
    actor_id: UUID
    allowed_zone_ids: frozenset[UUID]
    allowed_purpose_codes: frozenset[str]
    assignment_verified: bool
    can_manage_zones: bool
    can_manage_cameras: bool
    audit_purpose_code: str = AUDIT_PURPOSE_CODE

    def __post_init__(self) -> None:
        _nonzero(self.school_id)
        _nonzero(self.actor_id)
        for zone_id in self.allowed_zone_ids:
            _nonzero(zone_id)
        if not self.allowed_purpose_codes.issubset(CAMERA_PURPOSE_CODES):
            _fail()
        if self.audit_purpose_code != AUDIT_PURPOSE_CODE:
            _fail()

    def authorize_zone(self, zone_id: UUID, purpose_codes: tuple[str, ...]) -> None:
        if (
            not self.assignment_verified
            or not self.can_manage_cameras
            or zone_id not in self.allowed_zone_ids
            or not set(purpose_codes).issubset(self.allowed_purpose_codes)
        ):
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")

    def authorize_zone_management(self, zone_id: UUID | None = None) -> None:
        if not self.assignment_verified or not self.can_manage_zones:
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        if zone_id is not None and zone_id not in self.allowed_zone_ids:
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")


@dataclass(frozen=True, slots=True)
class ChangeMetadata:
    source_event_id: UUID
    audit_intent_id: UUID
    school_id: UUID
    actor_id: UUID
    request_id: str
    idempotency_key: str
    request_fingerprint: bytes
    policy_version: str
    changed_at: datetime

    def __post_init__(self) -> None:
        for value in (self.source_event_id, self.audit_intent_id, self.school_id, self.actor_id):
            _nonzero(value)
        _matches(self.request_id, REQUEST_ID)
        _matches(self.idempotency_key, IDEMPOTENCY_KEY)
        _matches(self.policy_version, STABLE_CODE)
        _aware(self.changed_at)
        if len(self.request_fingerprint) != 32:
            _fail()


@dataclass(frozen=True, slots=True)
class ZoneChangeRequest:
    metadata: ChangeMetadata
    zone_id: UUID
    operation: ZoneChangeOperation
    expected_version: int
    name: str | None = None
    purpose_codes: tuple[str, ...] | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        _nonzero(self.zone_id)
        _matches(self.reason_code, UPPER_CODE)
        if self.expected_version < 1:
            _fail()
        if self.operation is ZoneChangeOperation.UPDATE:
            if self.reason_code is not None or (self.name is None and self.purpose_codes is None):
                _fail()
        elif self.reason_code is None or self.name is not None or self.purpose_codes is not None:
            _fail()


@dataclass(frozen=True, slots=True)
class CameraChangeRequest:
    metadata: ChangeMetadata
    camera_id: UUID
    operation: CameraChangeOperation
    expected_version: int
    zone_id: UUID | None = None
    display_name: str | None = None
    purpose_codes: tuple[str, ...] | None = None
    source_id: UUID | None = None
    task_id: UUID | None = None
    mapping_purpose_code: str | None = None
    credential_ref: str | None = None
    schedule_version: str | None = None
    config_version: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        _nonzero(self.camera_id)
        _nonzero(self.zone_id)
        _nonzero(self.source_id)
        _nonzero(self.task_id)
        _matches(self.mapping_purpose_code, STABLE_CODE)
        _matches(self.credential_ref, SECRET_REFERENCE)
        _matches(self.schedule_version, STABLE_CODE)
        _matches(self.config_version, STABLE_CODE)
        _matches(self.reason_code, UPPER_CODE)
        if self.expected_version < 1:
            _fail()
        update_values = (self.zone_id, self.display_name, self.purpose_codes, self.config_version)
        mapping_values = (
            self.source_id,
            self.task_id,
            self.mapping_purpose_code,
            self.schedule_version,
            self.config_version,
        )
        if self.operation is CameraChangeOperation.UPDATE:
            if self.reason_code is not None or all(value is None for value in update_values):
                _fail()
            if (
                any(value is not None for value in mapping_values[:-1])
                or self.credential_ref is not None
            ):
                _fail()
        elif self.operation is CameraChangeOperation.MAP:
            if self.reason_code is not None or any(value is None for value in mapping_values):
                _fail()
            if (
                self.zone_id is not None
                or self.display_name is not None
                or self.purpose_codes is not None
            ):
                _fail()
        elif self.reason_code is None or any(
            value is not None
            for value in (
                *update_values,
                self.source_id,
                self.task_id,
                self.mapping_purpose_code,
                self.credential_ref,
                self.schedule_version,
            )
        ):
            _fail()


@dataclass(frozen=True, slots=True)
class CameraAuditIntent:
    audit_intent_id: UUID
    source_event_id: UUID
    school_id: UUID
    actor_id: UUID
    resource_type: str
    resource_id: UUID
    change_code: str
    changed_fields: tuple[str, ...]
    zone_id: UUID | None
    source_id: UUID | None
    task_id: UUID | None
    request_id: str
    idempotency_key: str
    request_fingerprint: bytes
    state_before: str | None
    state_after: str
    config_version: str | None
    schedule_version: str | None
    policy_version: str
    reason_code: str | None
    resulting_version: int
    created_at: datetime
    action: str = AUDIT_ACTION
    purpose_code: str = AUDIT_PURPOSE_CODE
    result: str = "success"

    def __post_init__(self) -> None:
        for value in (
            self.audit_intent_id,
            self.source_event_id,
            self.school_id,
            self.actor_id,
            self.resource_id,
        ):
            _nonzero(value)
        for optional_identifier in (self.zone_id, self.source_id, self.task_id):
            _nonzero(optional_identifier)
        if self.resource_type not in {"camera", "camera_zone"}:
            _fail()
        _matches(self.change_code, STABLE_CODE)
        _matches(self.request_id, REQUEST_ID)
        _matches(self.idempotency_key, IDEMPOTENCY_KEY)
        _matches(self.state_before, STABLE_CODE)
        _matches(self.state_after, STABLE_CODE)
        _matches(self.config_version, STABLE_CODE)
        _matches(self.schedule_version, STABLE_CODE)
        _matches(self.policy_version, STABLE_CODE)
        _matches(self.reason_code, UPPER_CODE)
        _aware(self.created_at)
        allowed_fields = {
            "ansvis_source",
            "config",
            "metadata",
            "purpose",
            "schedule",
            "status",
            "task",
            "zone",
        }
        if (
            self.action != AUDIT_ACTION
            or self.purpose_code != AUDIT_PURPOSE_CODE
            or self.result != "success"
            or not self.changed_fields
            or len(set(self.changed_fields)) != len(self.changed_fields)
            or not set(self.changed_fields).issubset(allowed_fields)
            or len(self.request_fingerprint) != 32
            or self.resulting_version < 1
        ):
            _fail()


@dataclass(frozen=True, slots=True)
class RegistryChangeOutcome:
    resource: Zone | Camera
    audit_intent: CameraAuditIntent
    duplicate: bool


def authorize_zone_compatibility(zone: Zone, purpose_codes: tuple[str, ...]) -> None:
    if zone.status is not ZoneStatus.ACTIVE:
        raise CameraRegistryError("CAMERA_ZONE_INACTIVE")
    if not set(purpose_codes).issubset(zone.purpose_codes):
        raise CameraRegistryError("CAMERA_PURPOSE_DENIED")


def update_zone(
    zone: Zone,
    *,
    name: str | None,
    purpose_codes: tuple[str, ...] | None,
    changed_at: datetime,
) -> Zone:
    if zone.status is not ZoneStatus.ACTIVE:
        raise CameraRegistryError("CAMERA_ZONE_INACTIVE")
    return replace(
        zone,
        name=zone.name if name is None else name,
        purpose_codes=zone.purpose_codes if purpose_codes is None else purpose_codes,
        updated_at=changed_at,
        row_version=zone.row_version + 1,
    )


def deactivate_zone(zone: Zone, *, changed_at: datetime) -> Zone:
    if zone.status is not ZoneStatus.ACTIVE:
        raise CameraRegistryError("CAMERA_TRANSITION_DENIED")
    return replace(
        zone,
        status=ZoneStatus.INACTIVE,
        deactivated_at=changed_at,
        updated_at=changed_at,
        row_version=zone.row_version + 1,
    )


def update_camera(
    camera: Camera,
    *,
    zone_id: UUID | None,
    display_name: str | None,
    purpose_codes: tuple[str, ...] | None,
    config_version: str | None,
    changed_at: datetime,
) -> Camera:
    if camera.status is CameraStatus.DISABLED:
        raise CameraRegistryError("CAMERA_TRANSITION_DENIED")
    return replace(
        camera,
        zone_id=camera.zone_id if zone_id is None else zone_id,
        display_name=camera.display_name if display_name is None else display_name,
        purpose_codes=camera.purpose_codes if purpose_codes is None else purpose_codes,
        config_version=camera.config_version if config_version is None else config_version,
        updated_at=changed_at,
        row_version=camera.row_version + 1,
    )


def map_camera(camera: Camera, request: CameraChangeRequest) -> Camera:
    if camera.status is CameraStatus.DISABLED:
        raise CameraRegistryError("CAMERA_TRANSITION_DENIED")
    if request.mapping_purpose_code not in camera.purpose_codes:
        raise CameraRegistryError("CAMERA_PURPOSE_DENIED")
    config_version = request.config_version
    if config_version is None:
        _fail()
    return replace(
        camera,
        source_id=request.source_id,
        task_id=request.task_id,
        mapping_purpose_code=request.mapping_purpose_code,
        credential_ref=request.credential_ref,
        schedule_version=request.schedule_version,
        config_version=config_version,
        updated_at=request.metadata.changed_at,
        row_version=camera.row_version + 1,
    )


def deactivate_camera(camera: Camera, *, changed_at: datetime) -> Camera:
    if camera.status is CameraStatus.DISABLED:
        raise CameraRegistryError("CAMERA_TRANSITION_DENIED")
    return replace(
        camera,
        status=CameraStatus.DISABLED,
        deactivated_at=changed_at,
        updated_at=changed_at,
        row_version=camera.row_version + 1,
    )
