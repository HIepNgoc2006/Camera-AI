from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from consent_service.application.service import ConsentApplicationService
from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    AuthorityType,
    Consent,
    ConsentAuditIntent,
    ConsentChangeOutcome,
    ConsentEvent,
    ConsentStatus,
    Purpose,
    SubjectType,
    TrustedConsentContext,
    TrustedPurposeContext,
)

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000001")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000002")
SUBJECT_ID = UUID("00000000-0000-4000-8000-000000000003")
AUTHORITY_ID = UUID("00000000-0000-4000-8000-000000000004")
IDS = [
    UUID("00000000-0000-4000-8000-000000000010"),
    UUID("00000000-0000-4000-8000-000000000011"),
    UUID("00000000-0000-4000-8000-000000000012"),
    UUID("00000000-0000-4000-8000-000000000013"),
]


class CapturingRepository:
    def __init__(self) -> None:
        self.purpose: Purpose | None = None
        self.created: ConsentChangeOutcome | None = None

    def register_purpose(self, purpose: Purpose) -> Purpose:
        self.purpose = purpose
        return purpose

    def get_purpose(self, purpose_id: UUID, school_id: UUID) -> Purpose | None:
        if self.purpose is None or self.purpose.purpose_id != purpose_id:
            return None
        return self.purpose if self.purpose.school_id in {None, school_id} else None

    def create_consent(
        self,
        consent: Consent,
        event: ConsentEvent,
        audit_intent: ConsentAuditIntent,
    ) -> ConsentChangeOutcome:
        self.created = ConsentChangeOutcome(consent, event, audit_intent, False)
        return self.created

    def transition_consent(self, request: object, context: object) -> ConsentChangeOutcome:
        raise AssertionError("not used")

    def get_for_evaluation(
        self, consent_id: UUID, school_id: UUID
    ) -> tuple[Consent | None, Purpose | None]:
        if self.created is None:
            return None, None
        return self.created.consent, self.purpose


def _purpose_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "code": "student_attendance",
        "description": "Synthetic attendance purpose.",
        "data_categories": ["attendance", "biometric"],
        "requires_biometric_consent": True,
        "status": "active",
        "version": 1,
        "valid_from": (NOW - timedelta(days=1)).isoformat(),
    }


def _request_payload(purpose_id: UUID) -> dict[str, object]:
    return {
        "schema_version": 1,
        "purpose_id": str(purpose_id),
        "subject_type": "student",
        "subject_id": str(SUBJECT_ID),
        "authority_type": "guardian",
        "authority_ref": str(AUTHORITY_ID),
        "scope_codes": ["attendance", "biometric"],
        "policy_version": "consent_v1",
        "valid_from": NOW.isoformat(),
        "request_id": "req_0123456789abcdef",
        "idempotency_key": "idem_test_value_01",
    }


def _context(*, verified: bool = True) -> TrustedConsentContext:
    return TrustedConsentContext(
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        subject_type=SubjectType.STUDENT,
        subject_id=SUBJECT_ID,
        authority_type=AuthorityType.GUARDIAN,
        authority_ref=AUTHORITY_ID,
        authority_verified=verified,
    )


def test_application_binds_trusted_context_and_emits_one_minimized_audit_intent() -> None:
    repository = CapturingRepository()
    generated = iter(IDS)
    service = ConsentApplicationService(
        repository,
        clock=lambda: NOW,
        identifier_factory=lambda: next(generated),
    )
    purpose = service.register_purpose(
        _purpose_payload(),
        TrustedPurposeContext(SCHOOL_ID, ACTOR_ID, can_manage_purposes=True),
    )
    outcome = service.request_consent(_request_payload(purpose.purpose_id), _context())

    assert outcome.consent.school_id == SCHOOL_ID
    assert outcome.consent.subject_id == SUBJECT_ID
    assert outcome.consent.status is ConsentStatus.PENDING
    assert outcome.event.consent_id == outcome.consent.consent_id
    assert outcome.audit_intent.consent_event_id == outcome.event.consent_event_id
    assert outcome.audit_intent.action == "CONSENT_REQUESTED"
    assert outcome.audit_intent.state_after == "pending"


def test_unverified_or_spoofed_authority_fails_before_persistence() -> None:
    repository = CapturingRepository()
    generated = iter(IDS)
    service = ConsentApplicationService(
        repository,
        clock=lambda: NOW,
        identifier_factory=lambda: next(generated),
    )
    purpose = service.register_purpose(
        _purpose_payload(),
        TrustedPurposeContext(SCHOOL_ID, ACTOR_ID, can_manage_purposes=True),
    )

    with pytest.raises(ConsentError, match="CONSENT_AUTHORITY_DENIED"):
        service.request_consent(_request_payload(purpose.purpose_id), _context(verified=False))

    spoofed = _request_payload(purpose.purpose_id)
    spoofed["subject_id"] = "00000000-0000-4000-8000-000000000099"
    with pytest.raises(ConsentError, match="CONSENT_AUTHORITY_DENIED"):
        service.request_consent(spoofed, _context())

    assert repository.created is None


def test_purpose_management_is_fail_closed() -> None:
    service = ConsentApplicationService(CapturingRepository(), clock=lambda: NOW)
    with pytest.raises(ConsentError, match="CONSENT_AUTHORITY_DENIED"):
        service.register_purpose(
            _purpose_payload(),
            TrustedPurposeContext(SCHOOL_ID, ACTOR_ID, can_manage_purposes=False),
        )
