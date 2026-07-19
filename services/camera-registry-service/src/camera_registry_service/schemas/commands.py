"""Strict V1 command DTOs for the trusted internal Camera Registry boundary."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
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

from camera_registry_service.domain.errors import CameraRegistryError
from camera_registry_service.domain.models import (
    CAMERA_PURPOSE_CODES,
    IDEMPOTENCY_KEY,
    REQUEST_ID,
    SECRET_REFERENCE,
    STABLE_CODE,
    UPPER_CODE,
    ZONE_PURPOSE_COMPATIBILITY,
    ZoneSensitivity,
    ZoneType,
)

PROHIBITED_TEXT = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|password|passwd|token|secret|authorization|"
    r"(?:^|\D)(?:\d{1,3}\.){3}\d{1,3}(?:\D|$)|@|\\)"
)


def _stable_code(value: str) -> str:
    if STABLE_CODE.fullmatch(value) is None:
        raise ValueError("value must be a stable code")
    return value


StableCode = Annotated[str, AfterValidator(_stable_code)]


class StrictCameraModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MutationModel(StrictCameraModel):
    schema_version: Literal[1]
    request_id: str = Field(min_length=12, max_length=124)
    idempotency_key: str = Field(min_length=13, max_length=125)
    policy_version: StableCode

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        if REQUEST_ID.fullmatch(value) is None:
            raise ValueError("request id must use the approved opaque format")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise ValueError("idempotency key must use the approved opaque format")
        return value

    def fingerprint(self) -> bytes:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return hashlib.sha256(encoded).digest()


def _validate_name(value: str) -> str:
    if PROHIBITED_TEXT.search(value) is not None:
        raise ValueError("operational name contains prohibited content")
    return value


def _validate_purposes(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value) or not set(value).issubset(CAMERA_PURPOSE_CODES):
        raise ValueError("purpose codes must be unique and approved")
    return tuple(sorted(value))


class RegisterZoneV1(MutationModel):
    code: StableCode
    name: str = Field(min_length=1, max_length=128)
    zone_type: ZoneType
    sensitivity: ZoneSensitivity = ZoneSensitivity.HIGH
    purpose_codes: tuple[StableCode, ...] = Field(min_length=1, max_length=7)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_name(value)

    @model_validator(mode="after")
    def validate_zone(self) -> Self:
        purposes = _validate_purposes(self.purpose_codes)
        if not set(purposes).issubset(ZONE_PURPOSE_COMPATIBILITY[self.zone_type]):
            raise ValueError("zone and purpose are incompatible")
        object.__setattr__(self, "purpose_codes", purposes)
        return self


class UpdateZoneV1(MutationModel):
    zone_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    purpose_codes: tuple[StableCode, ...] | None = Field(default=None, min_length=1, max_length=7)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return None if value is None else _validate_name(value)

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        if self.zone_id.int == 0 or (self.name is None and self.purpose_codes is None):
            raise ValueError("zone update must be scoped and non-empty")
        if self.purpose_codes is not None:
            object.__setattr__(self, "purpose_codes", _validate_purposes(self.purpose_codes))
        return self


class DeactivateZoneV1(MutationModel):
    zone_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    reason_code: str = Field(min_length=2, max_length=64)

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str) -> str:
        if UPPER_CODE.fullmatch(value) is None:
            raise ValueError("reason code must be an uppercase stable code")
        return value

    @model_validator(mode="after")
    def validate_zone_id(self) -> Self:
        if self.zone_id.int == 0:
            raise ValueError("zone identity must be non-zero")
        return self


class RegisterCameraV1(MutationModel):
    zone_id: UUID
    code: StableCode
    display_name: str = Field(min_length=1, max_length=128)
    purpose_codes: tuple[StableCode, ...] = Field(min_length=1, max_length=7)
    config_version: StableCode

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_name(value)

    @model_validator(mode="after")
    def validate_camera(self) -> Self:
        if self.zone_id.int == 0:
            raise ValueError("zone identity must be non-zero")
        object.__setattr__(self, "purpose_codes", _validate_purposes(self.purpose_codes))
        return self


class UpdateCameraV1(MutationModel):
    camera_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    zone_id: UUID | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    purpose_codes: tuple[StableCode, ...] | None = Field(default=None, min_length=1, max_length=7)
    config_version: StableCode | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return None if value is None else _validate_name(value)

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        if self.camera_id.int == 0 or (self.zone_id is not None and self.zone_id.int == 0):
            raise ValueError("camera and zone identities must be non-zero")
        if all(
            value is None
            for value in (self.zone_id, self.display_name, self.purpose_codes, self.config_version)
        ):
            raise ValueError("camera update must not be empty")
        if self.purpose_codes is not None:
            object.__setattr__(self, "purpose_codes", _validate_purposes(self.purpose_codes))
        return self


class MapCameraV1(MutationModel):
    camera_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    source_id: UUID
    task_id: UUID
    mapping_purpose_code: StableCode
    credential_ref: str | None = Field(default=None, min_length=39, max_length=103)
    schedule_version: StableCode
    config_version: StableCode

    @field_validator("credential_ref")
    @classmethod
    def validate_credential_ref(cls, value: str | None) -> str | None:
        if value is not None and SECRET_REFERENCE.fullmatch(value) is None:
            raise ValueError("credential reference must use the approved opaque format")
        return value

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        for identifier in (self.camera_id, self.source_id, self.task_id):
            if identifier.int == 0:
                raise ValueError("mapping identities must be non-zero")
        if self.mapping_purpose_code not in CAMERA_PURPOSE_CODES:
            raise ValueError("mapping purpose must be approved")
        return self


class DeactivateCameraV1(MutationModel):
    camera_id: UUID
    expected_version: int = Field(strict=True, ge=1)
    reason_code: str = Field(min_length=2, max_length=64)

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str) -> str:
        if UPPER_CODE.fullmatch(value) is None:
            raise ValueError("reason code must be an uppercase stable code")
        return value

    @model_validator(mode="after")
    def validate_camera_id(self) -> Self:
        if self.camera_id.int == 0:
            raise ValueError("camera identity must be non-zero")
        return self


def _parse(model: type[StrictCameraModel], value: Mapping[str, object]) -> StrictCameraModel:
    try:
        return model.model_validate(value)
    except ValidationError:
        raise CameraRegistryError("CAMERA_INPUT_INVALID") from None


def parse_register_zone(value: Mapping[str, object]) -> RegisterZoneV1:
    return RegisterZoneV1.model_validate(_parse(RegisterZoneV1, value))


def parse_update_zone(value: Mapping[str, object]) -> UpdateZoneV1:
    return UpdateZoneV1.model_validate(_parse(UpdateZoneV1, value))


def parse_deactivate_zone(value: Mapping[str, object]) -> DeactivateZoneV1:
    return DeactivateZoneV1.model_validate(_parse(DeactivateZoneV1, value))


def parse_register_camera(value: Mapping[str, object]) -> RegisterCameraV1:
    return RegisterCameraV1.model_validate(_parse(RegisterCameraV1, value))


def parse_update_camera(value: Mapping[str, object]) -> UpdateCameraV1:
    return UpdateCameraV1.model_validate(_parse(UpdateCameraV1, value))


def parse_map_camera(value: Mapping[str, object]) -> MapCameraV1:
    return MapCameraV1.model_validate(_parse(MapCameraV1, value))


def parse_deactivate_camera(value: Mapping[str, object]) -> DeactivateCameraV1:
    return DeactivateCameraV1.model_validate(_parse(DeactivateCameraV1, value))
