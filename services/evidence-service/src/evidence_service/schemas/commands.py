"""Strict, bounded API commands; media bytes are never accepted here."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from evidence_service.domain.models import (
    AccessAction,
    AccessRequest,
    ConsentState,
    MediaKind,
    UploadCommand,
)


class UploadRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    source_event_id: UUID
    camera_id: UUID | None = None
    task_id: UUID | None = None
    captured_at: datetime
    media_kind: MediaKind
    content_type: Literal["image/jpeg", "image/png", "image/webp", "video/mp4"]
    original_extension: str = Field(min_length=2, max_length=5)
    declared_size_bytes: StrictInt = Field(ge=1, le=250 * 1024 * 1024)
    sensitivity: Literal["high", "critical"]
    retention_policy_version: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{0,95}$")
    retention_days: Literal[15, 30, 180, 365]
    retention_expires_at: datetime

    @field_validator("captured_at", "retention_expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("EVIDENCE_REQUEST_INVALID")
        return value

    def command(self) -> UploadCommand:
        return UploadCommand(
            source_event_id=self.source_event_id,
            camera_id=self.camera_id,
            task_id=self.task_id,
            captured_at=self.captured_at,
            media_kind=self.media_kind,
            content_type=self.content_type,
            original_extension=self.original_extension,
            declared_size_bytes=self.declared_size_bytes,
            sensitivity=self.sensitivity,
            retention_policy_version=self.retention_policy_version,
            retention_days=self.retention_days,
            retention_expires_at=self.retention_expires_at,
        )


class AccessRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    evidence_id: UUID
    action: AccessAction
    ttl_seconds: StrictInt | None = Field(default=None, ge=1, le=300)
    consent_state: ConsentState
    reason_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_]{2,63}$",
    )
    approval_status: str = Field(
        default="not_required",
        pattern=r"^[a-z][a-z0-9_.:-]{0,95}$",
    )
    recipient_control_code: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_.:-]{0,95}$",
    )

    def command(self) -> AccessRequest:
        return AccessRequest(
            evidence_id=self.evidence_id,
            action=self.action,
            ttl_seconds=self.ttl_seconds,
            consent_state=self.consent_state,
            reason_code=self.reason_code,
            approval_status=self.approval_status,
            recipient_control_code=self.recipient_control_code,
        )
