"""Stable public response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictResponseModel(BaseModel):
    """Reject accidental response fields before they reach a client."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponseModel):
    """Minimal process-liveness response."""

    status: Literal["ok"] = "ok"
    request_id: str


class ErrorResponse(StrictResponseModel):
    """Stable error envelope shared by gateway endpoints."""

    error_code: str
    message: str
    request_id: str
