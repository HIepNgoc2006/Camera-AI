"""Minimal public response contracts for ANSVIS ingestion."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponseModel):
    status: Literal["ok"] = "ok"
    request_id: str


class ErrorResponse(StrictResponseModel):
    error_code: str
    message: str
    request_id: str


class IngestionAck(StrictResponseModel):
    schema_version: Literal["ansvis_http_trigger_ack_v1"] = "ansvis_http_trigger_ack_v1"
    outcome: Literal["accepted", "duplicate"]
    receipt_id: str = Field(pattern=r"^receipt_[A-Za-z0-9_-]{8,120}$")
    request_id: str
    correlation_id: str = Field(pattern=r"^corr_[A-Za-z0-9_-]{8,120}$")
