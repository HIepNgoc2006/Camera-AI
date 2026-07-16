"""Stable process response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponseModel):
    status: Literal["ok"] = "ok"
    request_id: str


class ErrorResponse(StrictResponseModel):
    error_code: str
    message: str
    request_id: str
