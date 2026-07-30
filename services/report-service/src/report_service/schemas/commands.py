"""Strict request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    report_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{0,95}$")
    school_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)
    class_ids: tuple[UUID, ...] = Field(max_length=1000)
    period_start: datetime
    period_end: datetime
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    approval_status: str
    format_code: str


class ExportAcceptedV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    export_id: UUID
    state: str
    expires_at: datetime
