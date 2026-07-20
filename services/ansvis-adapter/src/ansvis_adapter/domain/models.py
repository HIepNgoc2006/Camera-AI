"""Framework-free normalized ANSVIS event models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EventType(StrEnum):
    ATTENDANCE_FACE_OBSERVED = "attendance.face.observed"
    CAMERA_HEALTH_CHANGED = "camera.health.changed"
    EMOTION_OBSERVED = "insight.emotion.observed"
    TASK_HEALTH_CHANGED = "task.health.changed"
    TIMEKEEPING_FACE_OBSERVED = "timekeeping.face.observed"
    LITTERING_SUSPECTED = "violation.littering.suspected"
    PPE_SUSPECTED = "violation.ppe.suspected"
    SMOKING_SUSPECTED = "violation.smoking.suspected"
    UNIFORM_SUSPECTED = "violation.uniform.suspected"


class HealthStatus(StrEnum):
    DELAYED = "delayed"
    OFFLINE = "offline"
    ONLINE = "online"
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class EventAttributes:
    """Approved metadata only; media and raw vendor payloads have no representation."""

    track_id: str | None = None
    detection_key: str | None = None
    subject_external_id: str | None = None
    confidence: float | None = None
    status: HealthStatus | None = None
    model_version: str | None = None
    config_version: str | None = None
    rule_code: str | None = None
    detection_count: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseAnsvisEvent:
    """Common, normalized envelope shared by the typed event families."""

    source_namespace: str
    source_event_id: str | None
    event_type: EventType
    tenant_ref: str
    school_ref: str
    camera_external_id: str
    task_external_id: str
    occurred_at: datetime
    correlation_id: str
    attributes: EventAttributes

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")


@dataclass(frozen=True, slots=True, kw_only=True)
class FaceObservationEvent(BaseAnsvisEvent):
    """Attendance or staff-timekeeping face observation; not an attendance decision."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SuspectedViolationEvent(BaseAnsvisEvent):
    """A suspected rule violation requiring downstream policy and review."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EmotionInsightEvent(BaseAnsvisEvent):
    """A controlled insight event; not a disciplinary or identity decision."""


@dataclass(frozen=True, slots=True, kw_only=True)
class HealthStatusEvent(BaseAnsvisEvent):
    """Camera or ANSVIS task health transition."""


type NormalizedAnsvisEvent = (
    FaceObservationEvent | SuspectedViolationEvent | EmotionInsightEvent | HealthStatusEvent
)
