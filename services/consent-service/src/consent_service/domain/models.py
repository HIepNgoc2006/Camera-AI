"""Pure immutable models for purpose-scoped consent decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from consent_service.domain.errors import ConsentError

STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
UPPER_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
IDEMPOTENCY_KEY = re.compile(r"^idem_[A-Za-z0-9_-]{8,120}$")
EVIDENCE_REF = re.compile(
    r"^(authority_record|legal_basis_record):"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
APPROVED_DATA_CATEGORIES = frozenset(
    {
        "attendance",
        "biometric",
        "camera_event",
        "emotion",
        "evidence",
        "student_profile",
        "timekeeping",
        "violation",
    }
)


class PurposeStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class SubjectType(StrEnum):
    STUDENT = "student"
    STAFF = "staff"


class AuthorityType(StrEnum):
    SELF = "self"
    GUARDIAN = "guardian"
    LEGAL_BASIS = "legal_basis"


class ConsentStatus(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    RESTRICTED = "restricted"


class ConsentEventType(StrEnum):
    REQUESTED = "requested"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    RESTRICTED = "restricted"


class ConsentDecisionCode(StrEnum):
    ALLOWED = "CONSENT_ALLOWED"
    NOT_FOUND = "CONSENT_NOT_FOUND"
    SUBJECT_MISMATCH = "CONSENT_SUBJECT_MISMATCH"
    PURPOSE_MISMATCH = "CONSENT_PURPOSE_MISMATCH"
    AUTHORITY_DENIED = "CONSENT_AUTHORITY_DENIED"
    NOT_GRANTED = "CONSENT_NOT_GRANTED"
    WITHDRAWN = "CONSENT_WITHDRAWN"
    RESTRICTED = "CONSENT_RESTRICTED"
    EXPIRED = "CONSENT_EXPIRED"
    NOT_YET_VALID = "CONSENT_NOT_YET_VALID"
    PURPOSE_INACTIVE = "CONSENT_PURPOSE_INACTIVE"
    SCOPE_DENIED = "CONSENT_SCOPE_DENIED"
    STALE_VERSION = "CONSENT_STALE_VERSION"


def _aware(value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ConsentError("CONSENT_INPUT_INVALID")


def _nonzero(value: UUID | None) -> None:
    if value is not None and value.int == 0:
        raise ConsentError("CONSENT_INPUT_INVALID")


def _matches(value: str | None, pattern: re.Pattern[str]) -> None:
    if value is not None and pattern.fullmatch(value) is None:
        raise ConsentError("CONSENT_INPUT_INVALID")


def _stable_codes(values: tuple[str, ...], *, required: bool = True) -> None:
    if required and not values:
        raise ConsentError("CONSENT_INPUT_INVALID")
    if len(values) > 32 or len(set(values)) != len(values):
        raise ConsentError("CONSENT_INPUT_INVALID")
    for value in values:
        _matches(value, STABLE_CODE)


def _data_categories(values: tuple[str, ...]) -> None:
    _stable_codes(values)
    if not set(values).issubset(APPROVED_DATA_CATEGORIES):
        raise ConsentError("CONSENT_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class Purpose:
    purpose_id: UUID
    school_id: UUID | None
    code: str
    description: str
    data_categories: tuple[str, ...]
    requires_biometric_consent: bool
    status: PurposeStatus
    version: int
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        _nonzero(self.purpose_id)
        _nonzero(self.school_id)
        _matches(self.code, STABLE_CODE)
        _data_categories(self.data_categories)
        _aware(self.valid_from)
        _aware(self.valid_to)
        _aware(self.created_at)
        if not 1 <= self.version <= 2_147_483_647:
            raise ConsentError("CONSENT_INPUT_INVALID")
        if not 1 <= len(self.description) <= 512 or any(
            marker in self.description.casefold()
            for marker in ("data:", "base64", "rtsp://", "postgresql://", "password=")
        ):
            raise ConsentError("CONSENT_INPUT_INVALID")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ConsentError("CONSENT_INPUT_INVALID")

    def is_active_at(self, instant: datetime, school_id: UUID) -> bool:
        _aware(instant)
        return (
            self.status is PurposeStatus.ACTIVE
            and self.school_id in {None, school_id}
            and self.valid_from <= instant
            and (self.valid_to is None or instant < self.valid_to)
        )


@dataclass(frozen=True, slots=True)
class Consent:
    consent_id: UUID
    school_id: UUID
    subject_type: SubjectType
    subject_id: UUID
    purpose_id: UUID
    authority_type: AuthorityType
    authority_ref: UUID
    status: ConsentStatus
    scope_codes: tuple[str, ...]
    valid_from: datetime | None
    valid_to: datetime | None
    withdrawn_at: datetime | None
    restricted_at: datetime | None
    policy_version: str
    created_at: datetime
    updated_at: datetime
    row_version: int

    def __post_init__(self) -> None:
        for identifier in (
            self.consent_id,
            self.school_id,
            self.subject_id,
            self.purpose_id,
            self.authority_ref,
        ):
            _nonzero(identifier)
        _data_categories(self.scope_codes)
        _matches(self.policy_version, STABLE_CODE)
        for instant in (
            self.valid_from,
            self.valid_to,
            self.withdrawn_at,
            self.restricted_at,
            self.created_at,
            self.updated_at,
        ):
            _aware(instant)
        if self.row_version < 1 or self.updated_at < self.created_at:
            raise ConsentError("CONSENT_INPUT_INVALID")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to <= self.valid_from
        ):
            raise ConsentError("CONSENT_INPUT_INVALID")
        if self.status is ConsentStatus.GRANTED and self.valid_from is None:
            raise ConsentError("CONSENT_INPUT_INVALID")
        if (self.status is ConsentStatus.WITHDRAWN) != (self.withdrawn_at is not None):
            raise ConsentError("CONSENT_INPUT_INVALID")
        if (self.status is ConsentStatus.RESTRICTED) != (self.restricted_at is not None):
            raise ConsentError("CONSENT_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class TrustedConsentContext:
    """Authority and object relationship resolved outside publisher-controlled input."""

    school_id: UUID
    actor_id: UUID
    subject_type: SubjectType
    subject_id: UUID
    authority_type: AuthorityType
    authority_ref: UUID
    authority_verified: bool

    def __post_init__(self) -> None:
        for value in (self.school_id, self.actor_id, self.subject_id, self.authority_ref):
            _nonzero(value)


@dataclass(frozen=True, slots=True)
class TrustedPurposeContext:
    school_id: UUID | None
    actor_id: UUID
    can_manage_purposes: bool

    def __post_init__(self) -> None:
        _nonzero(self.school_id)
        _nonzero(self.actor_id)


@dataclass(frozen=True, slots=True)
class TrustedEvaluationContext:
    school_id: UUID
    subject_type: SubjectType
    subject_id: UUID
    relationship_verified: bool

    def __post_init__(self) -> None:
        for value in (self.school_id, self.subject_id):
            _nonzero(value)


@dataclass(frozen=True, slots=True)
class ConsentEvent:
    consent_event_id: UUID
    school_id: UUID
    consent_id: UUID
    event_type: ConsentEventType
    actor_id: UUID
    reason_code: str | None
    request_id: str
    evidence_ref: str | None
    idempotency_key: str
    request_fingerprint: bytes
    resulting_version: int
    occurred_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value in (self.consent_event_id, self.school_id, self.consent_id, self.actor_id):
            _nonzero(value)
        _matches(self.reason_code, UPPER_CODE)
        _matches(self.request_id, REQUEST_ID)
        _matches(self.evidence_ref, EVIDENCE_REF)
        _matches(self.idempotency_key, IDEMPOTENCY_KEY)
        _aware(self.occurred_at)
        _aware(self.recorded_at)
        if len(self.request_fingerprint) != 32 or self.resulting_version < 1:
            raise ConsentError("CONSENT_INPUT_INVALID")
        if (
            self.event_type
            in {
                ConsentEventType.DENIED,
                ConsentEventType.WITHDRAWN,
                ConsentEventType.EXPIRED,
                ConsentEventType.RESTRICTED,
            }
            and self.reason_code is None
        ):
            raise ConsentError("CONSENT_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class ConsentAuditIntent:
    audit_intent_id: UUID
    consent_event_id: UUID
    source_event_id: UUID
    school_id: UUID
    actor_id: UUID
    action: str
    purpose_code: str
    resource_id: UUID
    request_id: str
    result: str
    reason_code: str | None
    state_before: str | None
    state_after: str
    policy_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        for value in (
            self.audit_intent_id,
            self.consent_event_id,
            self.source_event_id,
            self.school_id,
            self.actor_id,
            self.resource_id,
        ):
            _nonzero(value)
        _matches(self.action, UPPER_CODE)
        _matches(self.purpose_code, STABLE_CODE)
        _matches(self.request_id, REQUEST_ID)
        _matches(self.result, STABLE_CODE)
        _matches(self.reason_code, UPPER_CODE)
        _matches(self.state_before, STABLE_CODE)
        _matches(self.state_after, STABLE_CODE)
        _matches(self.policy_version, STABLE_CODE)
        _aware(self.created_at)
        if self.result not in {"success", "denied"}:
            raise ConsentError("CONSENT_INPUT_INVALID")
        if (self.action == "CONSENT_DENIED") != (self.result == "denied"):
            raise ConsentError("CONSENT_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class ConsentChangeOutcome:
    consent: Consent
    event: ConsentEvent
    audit_intent: ConsentAuditIntent
    duplicate: bool


@dataclass(frozen=True, slots=True)
class ConsentTransitionRequest:
    consent_id: UUID
    target_status: ConsentStatus
    expected_version: int
    reason_code: str | None
    request_id: str
    evidence_ref: str | None
    idempotency_key: str
    request_fingerprint: bytes
    consent_event_id: UUID
    audit_intent_id: UUID
    changed_at: datetime

    def __post_init__(self) -> None:
        for value in (self.consent_id, self.consent_event_id, self.audit_intent_id):
            _nonzero(value)
        _matches(self.reason_code, UPPER_CODE)
        _matches(self.request_id, REQUEST_ID)
        _matches(self.evidence_ref, EVIDENCE_REF)
        _matches(self.idempotency_key, IDEMPOTENCY_KEY)
        _aware(self.changed_at)
        if self.expected_version < 1 or len(self.request_fingerprint) != 32:
            raise ConsentError("CONSENT_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class ConsentDecision:
    allowed: bool
    reason_code: ConsentDecisionCode
    consent_id: UUID | None = None
    consent_version: int | None = None


ALLOWED_TRANSITIONS: dict[ConsentStatus, frozenset[ConsentStatus]] = {
    ConsentStatus.PENDING: frozenset({ConsentStatus.GRANTED, ConsentStatus.DENIED}),
    ConsentStatus.GRANTED: frozenset(
        {ConsentStatus.WITHDRAWN, ConsentStatus.RESTRICTED, ConsentStatus.EXPIRED}
    ),
    ConsentStatus.DENIED: frozenset(),
    ConsentStatus.WITHDRAWN: frozenset(),
    ConsentStatus.EXPIRED: frozenset(),
    ConsentStatus.RESTRICTED: frozenset(),
}


def transition_consent(
    consent: Consent,
    target_status: ConsentStatus,
    *,
    changed_at: datetime,
) -> Consent:
    """Apply the small approved state machine; terminal states require a new record."""

    _aware(changed_at)
    if changed_at < consent.updated_at:
        raise ConsentError("CONSENT_INPUT_INVALID")
    if target_status not in ALLOWED_TRANSITIONS[consent.status]:
        raise ConsentError("CONSENT_TRANSITION_DENIED")
    valid_from = consent.valid_from
    if target_status is ConsentStatus.GRANTED and valid_from is None:
        valid_from = changed_at
    return replace(
        consent,
        status=target_status,
        valid_from=valid_from,
        withdrawn_at=changed_at if target_status is ConsentStatus.WITHDRAWN else None,
        restricted_at=changed_at if target_status is ConsentStatus.RESTRICTED else None,
        updated_at=changed_at,
        row_version=consent.row_version + 1,
    )
