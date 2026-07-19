"""Versioned strict command DTOs for the internal Consent Service boundary."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    APPROVED_DATA_CATEGORIES,
    AuthorityType,
    ConsentStatus,
    SubjectType,
)

STABLE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
UPPER_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
REQUEST_PATTERN = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
IDEMPOTENCY_PATTERN = re.compile(r"^idem_[A-Za-z0-9_-]{8,120}$")
EVIDENCE_REF_PATTERN = re.compile(
    r"^(authority_record|legal_basis_record):"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _stable_code(value: str) -> str:
    if STABLE_CODE_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a stable code")
    return value


StableCode = Annotated[str, AfterValidator(_stable_code)]


class StrictConsentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegisterPurposeV1(StrictConsentModel):
    schema_version: Literal[1]
    code: StableCode
    description: str = Field(min_length=1, max_length=512)
    data_categories: tuple[StableCode, ...] = Field(min_length=1, max_length=32)
    requires_biometric_consent: bool
    status: Literal["draft", "active"]
    version: int = Field(strict=True, ge=1, le=2_147_483_647)
    valid_from: datetime
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_purpose(self) -> Self:
        if len(set(self.data_categories)) != len(self.data_categories):
            raise ValueError("purpose categories must be unique")
        if not set(self.data_categories).issubset(APPROVED_DATA_CATEGORIES):
            raise ValueError("purpose categories must be approved")
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise ValueError("valid_from must include a timezone")
        if self.valid_to is not None:
            if self.valid_to.tzinfo is None or self.valid_to.utcoffset() is None:
                raise ValueError("valid_to must include a timezone")
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be later than valid_from")
        lowered = self.description.casefold()
        if any(
            marker in lowered
            for marker in ("data:", "base64", "rtsp://", "postgresql://", "password=")
        ):
            raise ValueError("description contains prohibited content")
        return self


class RequestConsentV1(StrictConsentModel):
    schema_version: Literal[1]
    purpose_id: UUID
    subject_type: SubjectType
    subject_id: UUID
    authority_type: AuthorityType
    authority_ref: UUID
    scope_codes: tuple[StableCode, ...] = Field(min_length=1, max_length=32)
    policy_version: StableCode
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    request_id: str = Field(min_length=12, max_length=124)
    idempotency_key: str = Field(min_length=13, max_length=125)
    evidence_ref: str | None = Field(default=None, max_length=128)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        if REQUEST_PATTERN.fullmatch(value) is None:
            raise ValueError("request id must use the approved opaque format")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if IDEMPOTENCY_PATTERN.fullmatch(value) is None:
            raise ValueError("idempotency key must use the approved opaque format")
        return value

    @field_validator("evidence_ref")
    @classmethod
    def validate_evidence_ref(cls, value: str | None) -> str | None:
        if value is not None and EVIDENCE_REF_PATTERN.fullmatch(value) is None:
            raise ValueError("evidence reference must be an approved opaque reference")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        for identifier in (self.purpose_id, self.subject_id, self.authority_ref):
            if identifier.int == 0:
                raise ValueError("opaque identifiers must be non-zero")
        if len(set(self.scope_codes)) != len(self.scope_codes):
            raise ValueError("scope codes must be unique")
        if not set(self.scope_codes).issubset(APPROVED_DATA_CATEGORIES):
            raise ValueError("scope codes must be approved")
        for instant in (self.valid_from, self.valid_to):
            if instant is not None and (instant.tzinfo is None or instant.utcoffset() is None):
                raise ValueError("validity timestamps must include a timezone")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to <= self.valid_from
        ):
            raise ValueError("valid_to must be later than valid_from")
        if self.valid_to is not None and self.valid_from is None:
            raise ValueError("valid_to requires valid_from")
        return self

    def fingerprint(self) -> bytes:
        return _fingerprint(self)


class TransitionConsentV1(StrictConsentModel):
    schema_version: Literal[1]
    consent_id: UUID
    target_status: Literal[
        ConsentStatus.GRANTED,
        ConsentStatus.DENIED,
        ConsentStatus.WITHDRAWN,
        ConsentStatus.EXPIRED,
        ConsentStatus.RESTRICTED,
    ]
    expected_version: int = Field(strict=True, ge=1)
    reason_code: str | None = Field(default=None, min_length=2, max_length=64)
    request_id: str = Field(min_length=12, max_length=124)
    idempotency_key: str = Field(min_length=13, max_length=125)
    evidence_ref: str | None = Field(default=None, max_length=128)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        if REQUEST_PATTERN.fullmatch(value) is None:
            raise ValueError("request id must use the approved opaque format")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if IDEMPOTENCY_PATTERN.fullmatch(value) is None:
            raise ValueError("idempotency key must use the approved opaque format")
        return value

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str | None) -> str | None:
        if value is not None and UPPER_CODE_PATTERN.fullmatch(value) is None:
            raise ValueError("reason code must be an uppercase stable code")
        return value

    @field_validator("evidence_ref")
    @classmethod
    def validate_evidence_ref(cls, value: str | None) -> str | None:
        if value is not None and EVIDENCE_REF_PATTERN.fullmatch(value) is None:
            raise ValueError("evidence reference must be an approved opaque reference")
        return value

    @model_validator(mode="after")
    def validate_transition(self) -> Self:
        if self.consent_id.int == 0:
            raise ValueError("consent identity must be non-zero")
        if (
            self.target_status
            in {
                ConsentStatus.DENIED,
                ConsentStatus.WITHDRAWN,
                ConsentStatus.EXPIRED,
                ConsentStatus.RESTRICTED,
            }
            and self.reason_code is None
        ):
            raise ValueError("the target status requires a stable reason code")
        return self

    def fingerprint(self) -> bytes:
        return _fingerprint(self)


class EvaluateConsentV1(StrictConsentModel):
    schema_version: Literal[1]
    consent_id: UUID
    purpose_id: UUID
    required_scope_codes: tuple[StableCode, ...] = Field(min_length=1, max_length=32)
    expected_version: int | None = Field(default=None, strict=True, ge=1)

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        if self.consent_id.int == 0 or self.purpose_id.int == 0:
            raise ValueError("opaque identifiers must be non-zero")
        if len(set(self.required_scope_codes)) != len(self.required_scope_codes):
            raise ValueError("required scope codes must be unique")
        if not set(self.required_scope_codes).issubset(APPROVED_DATA_CATEGORIES):
            raise ValueError("required scope codes must be approved")
        return self


def _fingerprint(model: BaseModel) -> bytes:
    encoded = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(encoded).digest()


def _parse(model: type[StrictConsentModel], value: Mapping[str, object]) -> StrictConsentModel:
    try:
        return model.model_validate(value)
    except ValidationError:
        raise ConsentError("CONSENT_INPUT_INVALID") from None


def parse_register_purpose(value: Mapping[str, object]) -> RegisterPurposeV1:
    return RegisterPurposeV1.model_validate(_parse(RegisterPurposeV1, value))


def parse_request_consent(value: Mapping[str, object]) -> RequestConsentV1:
    return RequestConsentV1.model_validate(_parse(RequestConsentV1, value))


def parse_transition_consent(value: Mapping[str, object]) -> TransitionConsentV1:
    return TransitionConsentV1.model_validate(_parse(TransitionConsentV1, value))


def parse_evaluate_consent(value: Mapping[str, object]) -> EvaluateConsentV1:
    return EvaluateConsentV1.model_validate(_parse(EvaluateConsentV1, value))
