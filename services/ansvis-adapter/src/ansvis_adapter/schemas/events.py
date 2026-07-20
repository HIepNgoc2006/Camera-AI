"""Strict V1 ANSVIS DTO parsing and normalization."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Literal, Never, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.models import (
    EmotionInsightEvent,
    EventAttributes,
    EventType,
    FaceObservationEvent,
    HealthStatus,
    HealthStatusEvent,
    NormalizedAnsvisEvent,
    SuspectedViolationEvent,
)

CONTRACT_VERSION = "ansvis_http_trigger_v1"
SAFE_INTEGER_MAX = 9_007_199_254_740_991
STABLE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
STABLE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
EXTERNAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CORRELATION_PATTERN = re.compile(r"^corr_[A-Za-z0-9_-]{8,120}$")
EVENT_TIME_PATTERN = re.compile(
    r"^(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})T"
    r"(?P<clock>[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?(?P<zone>Z|[+-][0-9]{2}:[0-9]{2})$"
)
FACE_EVENTS = frozenset({EventType.ATTENDANCE_FACE_OBSERVED, EventType.TIMEKEEPING_FACE_OBSERVED})
VIOLATION_EVENTS = frozenset(
    {
        EventType.LITTERING_SUSPECTED,
        EventType.PPE_SUSPECTED,
        EventType.SMOKING_SUSPECTED,
        EventType.UNIFORM_SUSPECTED,
    }
)
HEALTH_EVENTS = frozenset({EventType.CAMERA_HEALTH_CHANGED, EventType.TASK_HEALTH_CHANGED})

StrictCount = Annotated[int, Field(strict=True, ge=0, le=1000)]
StrictConfidence = Annotated[float, Field(strict=True, ge=0, le=1, multiple_of=0.000001)]


def _reject_constant(_: str) -> Never:
    raise AnsvisAdapterError("EVENT_SCHEMA_INVALID")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AnsvisAdapterError("EVENT_SCHEMA_INVALID")
        result[key] = value
    return result


def load_json_object(data: bytes) -> dict[str, object]:
    """Decode finite UTF-8 JSON and reject duplicate keys at every level."""

    try:
        value: object = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AnsvisAdapterError("EVENT_SCHEMA_INVALID") from None
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AnsvisAdapterError("EVENT_SCHEMA_INVALID")
    return value


def _normalize_external_id(value: object) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean is not an external identifier")
    if isinstance(value, int):
        if not 0 <= value <= SAFE_INTEGER_MAX:
            raise ValueError("integer external identifier is outside the I-JSON safe range")
        return str(value)
    if isinstance(value, str) and EXTERNAL_ID_PATTERN.fullmatch(value) is not None:
        return value
    raise ValueError("external identifier must use the approved opaque format")


def _stable_code(value: object) -> str:
    if isinstance(value, str) and STABLE_CODE_PATTERN.fullmatch(value) is not None:
        return value
    raise ValueError("value must be a stable lowercase code")


def _stable_ref(value: object) -> str:
    if isinstance(value, str) and STABLE_REF_PATTERN.fullmatch(value) is not None:
        return value
    raise ValueError("value must be an opaque stable reference")


def _event_time(value: str) -> datetime:
    if "T" in value and not value.endswith("Z") and not re.search(r"[+-][0-9]{2}:[0-9]{2}$", value):
        raise AnsvisAdapterError("TIME_TIMESTAMP_NAIVE")
    if not 20 <= len(value) <= 32:
        raise AnsvisAdapterError("TIME_TIMESTAMP_INVALID")
    matched = EVENT_TIME_PATTERN.fullmatch(value)
    if matched is None:
        raise AnsvisAdapterError("TIME_TIMESTAMP_INVALID")
    fraction = matched.group("fraction")
    if fraction is not None and len(fraction) > 6:
        raise AnsvisAdapterError("TIME_FRACTION_PRECISION")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AnsvisAdapterError("TIME_TIMESTAMP_INVALID") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnsvisAdapterError("TIME_TIMESTAMP_NAIVE")
    return parsed.astimezone(UTC)


class StrictEventModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EventAttributesV1(StrictEventModel):
    track_id: str | None = None
    detection_key: str | None = None
    subject_external_id: str | None = None
    confidence: StrictConfidence | None = None
    status: HealthStatus | None = None
    model_version: str | None = None
    config_version: str | None = None
    rule_code: str | None = None
    detection_count: StrictCount | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: object) -> object:
        if isinstance(value, Mapping) and any(child is None for child in value.values()):
            raise ValueError("attribute values cannot be null")
        return value

    @field_validator("track_id", "subject_external_id", mode="before")
    @classmethod
    def validate_external_ids(cls, value: object) -> str:
        return _normalize_external_id(value)

    @field_validator("detection_key", mode="before")
    @classmethod
    def validate_detection_key(cls, value: object) -> str:
        return _stable_ref(value)

    @field_validator("model_version", "config_version", "rule_code", mode="before")
    @classmethod
    def validate_codes(cls, value: object) -> str:
        return _stable_code(value)


class AnsvisHttpTriggerV1(StrictEventModel):
    schema_version: Literal["ansvis_http_trigger_v1"]
    source_namespace: str
    source_event_id: str | None
    event_type: EventType
    tenant_ref: str
    school_ref: str
    camera_external_id: str
    task_external_id: str
    event_time: datetime
    correlation_id: str
    attributes: EventAttributesV1

    @field_validator("source_namespace", mode="before")
    @classmethod
    def validate_source_namespace(cls, value: object) -> str:
        return _stable_code(value)

    @field_validator("source_event_id", mode="before")
    @classmethod
    def validate_source_event_id(cls, value: object) -> str | None:
        return None if value is None else _normalize_external_id(value)

    @field_validator("tenant_ref", "school_ref", mode="before")
    @classmethod
    def validate_stable_refs(cls, value: object) -> str:
        return _stable_ref(value)

    @field_validator("camera_external_id", "task_external_id", mode="before")
    @classmethod
    def validate_external_ids(cls, value: object) -> str:
        return _normalize_external_id(value)

    @field_validator("correlation_id")
    @classmethod
    def validate_correlation_id(cls, value: str) -> str:
        if CORRELATION_PATTERN.fullmatch(value) is None:
            raise ValueError("correlation id must use the approved opaque format")
        return value

    @model_validator(mode="after")
    def validate_conditional_fields(self) -> Self:
        if self.event_type in HEALTH_EVENTS and self.attributes.status is None:
            raise ValueError("health events require status")
        if self.source_event_id is None and (
            self.attributes.track_id is None or self.attributes.detection_key is None
        ):
            raise ValueError("fallback identity requires track and detection identifiers")
        return self


def declared_source_namespace(payload: Mapping[str, object]) -> str:
    """Read only the declared source needed before source authentication."""

    try:
        return _stable_code(payload.get("source_namespace"))
    except ValueError:
        raise AnsvisAdapterError("EVENT_SCHEMA_INVALID") from None


def parse_and_normalize_event(payload: Mapping[str, object]) -> NormalizedAnsvisEvent:
    """Validate the V1 DTO and map it to one typed, framework-free event family."""

    event_type = payload.get("event_type")
    if isinstance(event_type, str) and event_type not in {item.value for item in EventType}:
        raise AnsvisAdapterError("EVENT_TYPE_UNSUPPORTED")

    source_event_id = payload.get("source_event_id")
    attributes = payload.get("attributes")
    if (
        "source_event_id" in payload
        and source_event_id is None
        and isinstance(attributes, Mapping)
        and ("track_id" not in attributes or "detection_key" not in attributes)
    ):
        raise AnsvisAdapterError("EVENT_FALLBACK_IDENTITY_INSUFFICIENT")

    prepared = dict(payload)
    raw_event_time = payload.get("event_time")
    if not isinstance(raw_event_time, str):
        raise AnsvisAdapterError("EVENT_SCHEMA_INVALID")
    prepared["event_time"] = _event_time(raw_event_time)
    try:
        item = AnsvisHttpTriggerV1.model_validate(prepared)
    except ValidationError:
        raise AnsvisAdapterError("EVENT_SCHEMA_INVALID") from None

    normalized_attributes = EventAttributes(
        track_id=item.attributes.track_id,
        detection_key=item.attributes.detection_key,
        subject_external_id=item.attributes.subject_external_id,
        confidence=item.attributes.confidence,
        status=item.attributes.status,
        model_version=item.attributes.model_version,
        config_version=item.attributes.config_version,
        rule_code=item.attributes.rule_code,
        detection_count=item.attributes.detection_count,
    )
    if item.event_type in FACE_EVENTS:
        return FaceObservationEvent(
            source_namespace=item.source_namespace,
            source_event_id=item.source_event_id,
            event_type=item.event_type,
            tenant_ref=item.tenant_ref,
            school_ref=item.school_ref,
            camera_external_id=item.camera_external_id,
            task_external_id=item.task_external_id,
            occurred_at=item.event_time,
            correlation_id=item.correlation_id,
            attributes=normalized_attributes,
        )
    if item.event_type in VIOLATION_EVENTS:
        return SuspectedViolationEvent(
            source_namespace=item.source_namespace,
            source_event_id=item.source_event_id,
            event_type=item.event_type,
            tenant_ref=item.tenant_ref,
            school_ref=item.school_ref,
            camera_external_id=item.camera_external_id,
            task_external_id=item.task_external_id,
            occurred_at=item.event_time,
            correlation_id=item.correlation_id,
            attributes=normalized_attributes,
        )
    if item.event_type is EventType.EMOTION_OBSERVED:
        return EmotionInsightEvent(
            source_namespace=item.source_namespace,
            source_event_id=item.source_event_id,
            event_type=item.event_type,
            tenant_ref=item.tenant_ref,
            school_ref=item.school_ref,
            camera_external_id=item.camera_external_id,
            task_external_id=item.task_external_id,
            occurred_at=item.event_time,
            correlation_id=item.correlation_id,
            attributes=normalized_attributes,
        )
    if item.event_type in HEALTH_EVENTS:
        return HealthStatusEvent(
            source_namespace=item.source_namespace,
            source_event_id=item.source_event_id,
            event_type=item.event_type,
            tenant_ref=item.tenant_ref,
            school_ref=item.school_ref,
            camera_external_id=item.camera_external_id,
            task_external_id=item.task_external_id,
            occurred_at=item.event_time,
            correlation_id=item.correlation_id,
            attributes=normalized_attributes,
        )
    raise AnsvisAdapterError("EVENT_TYPE_UNSUPPORTED")
