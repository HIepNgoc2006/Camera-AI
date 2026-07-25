"""Strict versioned internal commands for Timekeeping Service use cases."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from timekeeping_service.domain.errors import TimekeepingError
from timekeeping_service.domain.models import (
    CORRECTION_REASON_CODES,
    REQUEST_ID,
    UPPER_CODE,
    ApprovalStatus,
    LinkType,
    TimekeepingStatus,
)

OPAQUE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class StrictTimekeepingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ApplyNormalizedTimekeepingEventV1(StrictTimekeepingModel):
    schema_version: Literal[1]
    normalized_event_id: UUID
    staff_id: UUID
    shift_id: UUID
    occurred_at: datetime
    link_type: LinkType
    decision_confidence: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("1"),
        max_digits=5,
        decimal_places=4,
    )
    retention_until: datetime

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if any(
            value.int == 0 for value in (self.normalized_event_id, self.staff_id, self.shift_id)
        ):
            raise ValueError("event identities must be non-zero")
        for value in (self.occurred_at, self.retention_until):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("event timestamps must include a timezone")
        if self.retention_until <= self.occurred_at:
            raise ValueError("retention must extend beyond event time")
        if self.link_type is LinkType.REJECTED:
            raise ValueError("rejected links are derived by consent policy")
        return self


class CorrectTimekeepingV1(StrictTimekeepingModel):
    schema_version: Literal[1]
    timekeeping_record_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    to_status: TimekeepingStatus
    to_check_in_at: datetime | None = None
    to_check_out_at: datetime | None = None
    reason_code: str = Field(min_length=2, max_length=64)
    approval_status: ApprovalStatus
    request_id: str = Field(min_length=12, max_length=124)

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str) -> str:
        if UPPER_CODE.fullmatch(value) is None or value not in CORRECTION_REASON_CODES:
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
        if self.timekeeping_record_id.int == 0:
            raise ValueError("timekeeping identity must be non-zero")
        for value in (self.to_check_in_at, self.to_check_out_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("timekeeping timestamps must include a timezone")
        if (
            self.to_check_in_at is not None
            and self.to_check_out_at is not None
            and self.to_check_out_at < self.to_check_in_at
        ):
            raise ValueError("check-out cannot precede check-in")
        return self


def _parse(
    model: type[StrictTimekeepingModel],
    value: Mapping[str, object],
) -> StrictTimekeepingModel:
    try:
        return model.model_validate(value)
    except ValidationError:
        raise TimekeepingError("TIMEKEEPING_INPUT_INVALID") from None


def parse_apply_event(value: Mapping[str, object]) -> ApplyNormalizedTimekeepingEventV1:
    return ApplyNormalizedTimekeepingEventV1.model_validate(
        _parse(ApplyNormalizedTimekeepingEventV1, value)
    )


def parse_correction(value: Mapping[str, object]) -> CorrectTimekeepingV1:
    return CorrectTimekeepingV1.model_validate(_parse(CorrectTimekeepingV1, value))
