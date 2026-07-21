"""Strict V1 command DTOs for the trusted internal attendance boundary."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from attendance_service.domain.errors import AttendanceError
from attendance_service.domain.models import (
    CORRECTION_REASON_CODES,
    REQUEST_ID,
    UPPER_CODE,
    ApprovalStatus,
    AttendanceStatus,
    LinkType,
)


class StrictAttendanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ApplyNormalizedEventV1(StrictAttendanceModel):
    schema_version: Literal[1]
    normalized_event_id: UUID
    student_id: UUID
    class_id: UUID
    occurred_at: datetime
    link_type: LinkType
    decision_confidence: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("1"),
        max_digits=5,
        decimal_places=4,
    )
    school_timezone: str = Field(min_length=1, max_length=64)
    retention_until: datetime

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if any(
            value.int == 0 for value in (self.normalized_event_id, self.student_id, self.class_id)
        ):
            raise ValueError("event identities must be non-zero")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        if self.retention_until.tzinfo is None or self.retention_until.utcoffset() is None:
            raise ValueError("retention_until must include a timezone")
        if self.retention_until <= self.occurred_at:
            raise ValueError("retention must extend beyond event time")
        try:
            ZoneInfo(self.school_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("school timezone must be an installed IANA timezone") from exc
        return self


class CorrectAttendanceV1(StrictAttendanceModel):
    schema_version: Literal[1]
    attendance_record_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    to_status: AttendanceStatus
    to_check_in_at: datetime | None = None
    reason_code: str = Field(min_length=2, max_length=64)
    approval_status: ApprovalStatus
    request_id: str = Field(min_length=12, max_length=124)

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str) -> str:
        if UPPER_CODE.fullmatch(value) is None:
            raise ValueError("reason code must be an uppercase stable code")
        if value not in CORRECTION_REASON_CODES:
            raise ValueError("reason code must be approved")
        return value

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        if REQUEST_ID.fullmatch(value) is None:
            raise ValueError("request id must use the approved opaque format")
        return value

    @model_validator(mode="after")
    def validate_correction(self) -> Self:
        if self.attendance_record_id.int == 0:
            raise ValueError("attendance identity must be non-zero")
        if self.to_check_in_at is not None and (
            self.to_check_in_at.tzinfo is None or self.to_check_in_at.utcoffset() is None
        ):
            raise ValueError("attendance timestamps must include a timezone")
        return self


def _parse(
    model: type[StrictAttendanceModel], value: Mapping[str, object]
) -> StrictAttendanceModel:
    try:
        return model.model_validate(value)
    except ValidationError:
        raise AttendanceError("ATTENDANCE_INPUT_INVALID") from None


def parse_apply_event(value: Mapping[str, object]) -> ApplyNormalizedEventV1:
    return ApplyNormalizedEventV1.model_validate(_parse(ApplyNormalizedEventV1, value))


def parse_correction(value: Mapping[str, object]) -> CorrectAttendanceV1:
    return CorrectAttendanceV1.model_validate(_parse(CorrectAttendanceV1, value))
