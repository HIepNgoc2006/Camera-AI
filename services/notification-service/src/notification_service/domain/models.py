"""Immutable notification records and trusted authorization snapshots."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from notification_service.domain.errors import NotificationError

STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
SERVICE_CODE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
CORRELATION_ID = re.compile(r"^cor_[A-Za-z0-9_-]{8,120}$")
IDEMPOTENCY_KEY = re.compile(r"^ntf_[A-Za-z0-9_-]{12,120}$")
POLICY_VERSION = "notification_privacy_policy_v1"


def _aware(*values: datetime | None) -> None:
    if any(
        value is not None and (value.tzinfo is None or value.utcoffset() is None)
        for value in values
    ):
        raise NotificationError("NOTIFICATION_REQUEST_INVALID")


def _nonzero(*values: UUID | None) -> None:
    if any(value is not None and value.int == 0 for value in values):
        raise NotificationError("NOTIFICATION_REQUEST_INVALID")


def _code(value: str, pattern: re.Pattern[str] = STABLE_CODE) -> None:
    if pattern.fullmatch(value) is None:
        raise NotificationError("NOTIFICATION_REQUEST_INVALID")


class Channel(StrEnum):
    IN_APP = "in_app"
    PUSH = "push"
    EMAIL = "email"


class ContentClass(StrEnum):
    ATTENDANCE_UPDATE = "attendance_update"
    TIMEKEEPING_UPDATE = "timekeeping_update"
    VIOLATION_UPDATE = "violation_update"
    CORRECTION_UPDATE = "correction_update"
    PRIVACY_ACTION = "privacy_action"
    OPERATIONAL_ALERT = "operational_alert"


class ConsentDecision(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"
    UNAVAILABLE = "unavailable"


class DeliveryState(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTERED = "dead_lettered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class EndpointKind(StrEnum):
    DEVICE_TOKEN = "device_token"
    EMAIL = "email"


class EndpointState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class AttemptResult(StrEnum):
    DELIVERED = "delivered"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTERED = "dead_lettered"
    CANCELLED = "cancelled"


class ProviderResultCategory(StrEnum):
    """Provider-neutral outcomes; raw provider messages never cross this boundary."""

    ACCEPTED = "accepted"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    RATE_LIMITED = "rate_limited"
    INVALID_ENDPOINT = "invalid_endpoint"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class TrustedSourceContext:
    source_service: str
    tenant_id: UUID
    school_id: UUID
    trusted_identity: bool
    permission_codes: frozenset[str]
    delegation_authorized: bool
    runtime_approvals_complete: bool
    policy_version: str

    def __post_init__(self) -> None:
        _code(self.source_service, SERVICE_CODE)
        _nonzero(self.tenant_id, self.school_id)
        if any(STABLE_CODE.fullmatch(code) is None for code in self.permission_codes):
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class NotificationCommand:
    source_event_id: UUID
    idempotency_key: str
    tenant_id: UUID
    school_id: UUID
    subject_ref: UUID
    resource_ref: UUID
    content_class: ContentClass
    template_code: str
    template_version: int
    source_state: str
    source_expires_at: datetime
    notification_expires_at: datetime
    recipient_refs: tuple[UUID, ...]
    channels: tuple[Channel, ...]
    request_id: str
    correlation_id: str

    def __post_init__(self) -> None:
        _nonzero(
            self.source_event_id,
            self.tenant_id,
            self.school_id,
            self.subject_ref,
            self.resource_ref,
            *self.recipient_refs,
        )
        _code(self.idempotency_key, IDEMPOTENCY_KEY)
        _code(self.template_code)
        _code(self.source_state)
        _code(self.request_id, REQUEST_ID)
        _code(self.correlation_id, CORRELATION_ID)
        _aware(self.source_expires_at, self.notification_expires_at)
        if (
            self.template_version != 1
            or not 1 <= len(self.recipient_refs) <= 100
            or len(set(self.recipient_refs)) != len(self.recipient_refs)
            or not 1 <= len(self.channels) <= len(Channel)
            or len(set(self.channels)) != len(self.channels)
            or self.notification_expires_at > self.source_expires_at
        ):
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class RecipientAuthorization:
    recipient_ref: UUID
    tenant_id: UUID
    school_id: UUID
    recipient_role: str
    relationship_code: str
    permission_code: str
    purpose_code: str
    recipient_active: bool
    relationship_current: bool
    permission_current: bool
    purpose_active: bool
    consent_decision: ConsentDecision
    source_current: bool
    endpoint_active: bool
    endpoint_verified: bool
    endpoint_owned: bool
    channel_preference_enabled: bool
    dependencies_available: bool

    def __post_init__(self) -> None:
        _nonzero(self.recipient_ref, self.tenant_id, self.school_id)
        for value in (
            self.recipient_role,
            self.relationship_code,
            self.permission_code,
            self.purpose_code,
        ):
            _code(value)


@dataclass(frozen=True, slots=True)
class RenderedContent:
    channel: Channel
    fields: Mapping[str, str | int | bool]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True, slots=True)
class NotificationIntent:
    notification_id: UUID
    command: NotificationCommand
    purpose_code: str
    policy_version: str
    created_at: datetime
    state: str = "pending"

    def __post_init__(self) -> None:
        _nonzero(self.notification_id)
        _aware(self.created_at)
        _code(self.purpose_code)
        _code(self.policy_version)
        _code(self.state)


@dataclass(frozen=True, slots=True)
class RecipientDelivery:
    delivery_id: UUID
    notification_id: UUID
    recipient_ref: UUID
    channel: Channel
    content: RenderedContent
    state: DeliveryState
    attempt_count: int
    next_attempt_at: datetime | None
    expires_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        _nonzero(self.delivery_id, self.notification_id, self.recipient_ref)
        _aware(self.next_attempt_at, self.expires_at, self.created_at)
        if (
            not 0 <= self.attempt_count <= 5
            or self.expires_at <= self.created_at
            or (self.state is DeliveryState.RETRY_SCHEDULED) != (self.next_attempt_at is not None)
        ):
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class DeliveryAttempt:
    attempt_id: UUID
    delivery_id: UUID
    attempt_number: int
    result: AttemptResult
    stable_provider_result_category: str
    occurred_at: datetime
    next_attempt_at: datetime | None

    def __post_init__(self) -> None:
        _nonzero(self.attempt_id, self.delivery_id)
        _aware(self.occurred_at, self.next_attempt_at)
        _code(self.stable_provider_result_category)
        if not 1 <= self.attempt_number <= 5:
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class ProtectedEndpoint:
    endpoint_id: UUID
    tenant_id: UUID
    recipient_ref: UUID
    kind: EndpointKind
    ciphertext: bytes
    lookup_digest: bytes
    state: EndpointState
    verified_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        _nonzero(self.endpoint_id, self.tenant_id, self.recipient_ref)
        _aware(self.verified_at, self.created_at)
        if not self.ciphertext.startswith(b"ENCV1") or len(self.lookup_digest) != 32:
            raise NotificationError("NOTIFICATION_ENDPOINT_DENIED")

    def __repr__(self) -> str:
        return (
            "ProtectedEndpoint(endpoint_id=<opaque>, tenant_id=<opaque>, "
            "recipient_ref=<opaque>, kind=<redacted>, ciphertext=<redacted>, "
            "lookup_digest=<redacted>, state=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class NotificationOutcome:
    notification_id: UUID
    queued_deliveries: int
    denied_recipients: int
    duplicate: bool

    def __post_init__(self) -> None:
        _nonzero(self.notification_id)
        if self.queued_deliveries < 0 or self.denied_recipients < 0:
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class DeliveryWorkItem:
    """Minimum aggregate required for a fresh delivery/open authorization check."""

    intent: NotificationIntent
    delivery: RecipientDelivery

    def __post_init__(self) -> None:
        if self.intent.notification_id != self.delivery.notification_id:
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class DeadLetterEnvelope:
    """Content-free reconciliation record safe for the shared DLQ topology."""

    delivery_id: UUID
    notification_id: UUID
    attempt_count: int
    reason_category: ProviderResultCategory
    occurred_at: datetime

    def __post_init__(self) -> None:
        _nonzero(self.delivery_id, self.notification_id)
        _aware(self.occurred_at)
        if not 1 <= self.attempt_count <= 5:
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class OpenGrant:
    """Opaque fields returned only after a current recipient authorization check."""

    notification_id: UUID
    resource_ref: UUID
    template_code: str

    def __post_init__(self) -> None:
        _nonzero(self.notification_id, self.resource_ref)
        _code(self.template_code)
