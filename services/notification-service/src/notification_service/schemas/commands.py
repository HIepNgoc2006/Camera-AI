"""Strict versioned DTOs for trusted internal notification requests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from notification_service.domain.errors import NotificationError
from notification_service.domain.models import Channel, ContentClass, NotificationCommand


class NotificationIntentV1(BaseModel):
    # Internal callers still cross a JSON boundary, so enums, UUIDs, and datetimes
    # must accept their canonical JSON representations. Constraints and
    # ``extra="forbid"`` keep the contract closed without relying on Python-only
    # object instances.
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    source_event_id: UUID
    idempotency_key: Annotated[str, Field(pattern=r"^ntf_[A-Za-z0-9_-]{12,120}$")]
    tenant_id: UUID
    school_id: UUID
    subject_ref: UUID
    resource_ref: UUID
    content_class: Annotated[ContentClass, Field(strict=False)]
    template_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.:-]{0,95}$")]
    template_version: Literal[1]
    source_state: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.:-]{0,95}$")]
    source_expires_at: datetime
    notification_expires_at: datetime
    recipient_refs: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=100)]
    channels: Annotated[
        tuple[Annotated[Channel, Field(strict=False)], ...],
        Field(min_length=1, max_length=3),
    ]
    request_id: Annotated[str, Field(pattern=r"^req_[A-Za-z0-9_-]{8,120}$")]
    correlation_id: Annotated[str, Field(pattern=r"^cor_[A-Za-z0-9_-]{8,120}$")]


def parse_notification_intent(payload: Mapping[str, object]) -> NotificationCommand:
    try:
        raw_payload = dict(payload)
        if any(
            type(raw_payload.get(field)) is not int
            for field in ("schema_version", "template_version")
        ):
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")
        try:
            command = NotificationIntentV1.model_validate(raw_payload)
        except ValidationError:
            # Strict Python validation deliberately accepts only already-typed
            # values. Retry through Pydantic's strict JSON path so canonical
            # UUID/datetime strings and arrays from a decoded JSON boundary are
            # accepted without enabling broad Python coercion.
            encoded_payload = json.dumps(
                raw_payload,
                allow_nan=False,
                separators=(",", ":"),
            )
            command = NotificationIntentV1.model_validate_json(encoded_payload)
        return NotificationCommand(
            source_event_id=command.source_event_id,
            idempotency_key=command.idempotency_key,
            tenant_id=command.tenant_id,
            school_id=command.school_id,
            subject_ref=command.subject_ref,
            resource_ref=command.resource_ref,
            content_class=command.content_class,
            template_code=command.template_code,
            template_version=command.template_version,
            source_state=command.source_state,
            source_expires_at=command.source_expires_at,
            notification_expires_at=command.notification_expires_at,
            recipient_refs=command.recipient_refs,
            channels=command.channels,
            request_id=command.request_id,
            correlation_id=command.correlation_id,
        )
    except (TypeError, ValueError, ValidationError, NotificationError):
        raise NotificationError("NOTIFICATION_REQUEST_INVALID") from None
