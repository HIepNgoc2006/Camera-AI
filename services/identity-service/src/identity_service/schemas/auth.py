"""Strict authentication request and response schemas."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(min_length=1, max_length=254)]
Password = Annotated[str, Field(min_length=1, max_length=1024)]
TotpCode = Annotated[str, Field(pattern=r"^\d{6}$")]
RefreshToken = Annotated[str, Field(min_length=32, max_length=1024)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    tenant_id: UUID
    identifier: Identifier
    password: Password
    mfa_code: TotpCode | None = None


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: RefreshToken


class MfaEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: Annotated[str, Field(min_length=16, max_length=128)]
    code: TotpCode


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"]
    expires_in: int
    session_id: UUID
    mfa_verified: bool
    request_id: str


class OperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    affected_sessions: int | None = None
    factor_id: UUID | None = None
    request_id: str
