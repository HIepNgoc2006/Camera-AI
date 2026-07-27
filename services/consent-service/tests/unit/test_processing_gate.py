"""Issue #139 processing-gate matrix: strict tri-state output, deny on ambiguity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from consent_service.application.ports import ConsentRepository
from consent_service.application.service import ConsentApplicationService
from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    AuthorityType,
    Consent,
    ConsentStatus,
    Purpose,
    PurposeStatus,
    SubjectType,
    TrustedProcessingContext,
)
from consent_service.domain.processing import (
    PROCESSING_GATE_POLICY_VERSION,
    ProcessingConsentStatus,
    ProcessingLookup,
)

NOW = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER_SCHOOL_ID = UUID("00000000-0000-4000-8000-0000000000a2")
SUBJECT_ID = UUID("00000000-0000-4000-8000-0000000000b1")
AUTHORITY_ID = UUID("00000000-0000-4000-8000-0000000000b2")
PURPOSE_ID = UUID("00000000-0000-4000-8000-0000000000c1")
PURPOSE_V2_ID = UUID("00000000-0000-4000-8000-0000000000c2")
CONSENT_ID = UUID("00000000-0000-4000-8000-0000000000d1")


def _purpose(
    *,
    purpose_id: UUID = PURPOSE_ID,
    school_id: UUID | None = SCHOOL_ID,
    status: PurposeStatus = PurposeStatus.ACTIVE,
    requires_biometric_consent: bool = True,
    version: int = 1,
    valid_to: datetime | None = None,
) -> Purpose:
    return Purpose(
        purpose_id=purpose_id,
        school_id=school_id,
        code="attendance",
        description="Synthetic attendance processing purpose.",
        data_categories=("attendance", "biometric"),
        requires_biometric_consent=requires_biometric_consent,
        status=status,
        version=version,
        valid_from=NOW - timedelta(days=30),
        valid_to=valid_to,
        created_at=NOW - timedelta(days=30),
    )


def _consent(
    *,
    status: ConsentStatus = ConsentStatus.GRANTED,
    purpose_id: UUID = PURPOSE_ID,
    school_id: UUID = SCHOOL_ID,
    scope_codes: tuple[str, ...] = ("attendance", "biometric"),
    valid_from: datetime | None = NOW - timedelta(days=7),
    valid_to: datetime | None = None,
    withdrawn_at: datetime | None = None,
    restricted_at: datetime | None = None,
) -> Consent:
    return Consent(
        consent_id=CONSENT_ID,
        school_id=school_id,
        subject_type=SubjectType.STUDENT,
        subject_id=SUBJECT_ID,
        purpose_id=purpose_id,
        authority_type=AuthorityType.GUARDIAN,
        authority_ref=AUTHORITY_ID,
        status=status,
        scope_codes=scope_codes,
        valid_from=valid_from,
        valid_to=valid_to,
        withdrawn_at=withdrawn_at,
        restricted_at=restricted_at,
        policy_version="consent_policy_v1",
        created_at=NOW - timedelta(days=7),
        updated_at=NOW - timedelta(days=6),
        row_version=2,
    )


class StubRepository:
    """Serve one canned lookup; every mutation entry point stays unreachable."""

    def __init__(self, lookup: ProcessingLookup, *, unavailable: bool = False) -> None:
        self.lookup = lookup
        self.unavailable = unavailable
        self.calls: list[tuple[UUID, SubjectType, UUID | None, str]] = []

    def register_purpose(self, purpose: object) -> object:
        raise AssertionError("not used")

    def get_purpose(self, purpose_id: object, school_id: object) -> object:
        raise AssertionError("not used")

    def create_consent(self, consent: object, event: object, audit_intent: object) -> object:
        raise AssertionError("not used")

    def transition_consent(self, request: object, context: object) -> object:
        raise AssertionError("not used")

    def get_for_evaluation(self, consent_id: object, school_id: object) -> object:
        raise AssertionError("not used")

    def find_for_processing(
        self,
        *,
        school_id: UUID,
        subject_type: SubjectType,
        subject_id: UUID | None,
        purpose_code: str,
    ) -> ProcessingLookup:
        if self.unavailable:
            raise ConsentError("CONSENT_UNAVAILABLE")
        self.calls.append((school_id, subject_type, subject_id, purpose_code))
        return self.lookup


def _service(repository: StubRepository) -> ConsentApplicationService:
    return ConsentApplicationService(cast(ConsentRepository, repository), clock=lambda: NOW)


def _payload(
    *,
    subject_ref: str | None = str(SUBJECT_ID),
    purpose: str = "attendance",
    policy_version: str = PROCESSING_GATE_POLICY_VERSION,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "tenant_ref": "tenant-01",
        "school_ref": "school-01",
        "subject_ref": subject_ref,
        "purpose": purpose,
        "policy_version": policy_version,
    }


def _context(*, authorized: bool = True) -> TrustedProcessingContext:
    return TrustedProcessingContext(
        school_id=SCHOOL_ID,
        source_service="event-ingestion-service",
        gate_authorized=authorized,
    )


def test_granted_consent_is_allowed_with_the_consent_policy_version() -> None:
    repository = StubRepository(ProcessingLookup((_purpose(),), (_consent(),)))
    decision = _service(repository).evaluate_processing(_payload(), _context())
    assert decision.status is ProcessingConsentStatus.ALLOWED
    assert decision.reason_code == "CONSENT_ALLOWED"
    assert decision.policy_version == "consent_policy_v1"
    assert repository.calls == [(SCHOOL_ID, SubjectType.STUDENT, SUBJECT_ID, "attendance")]


@pytest.mark.parametrize(
    ("consent", "expected_reason"),
    [
        (
            _consent(status=ConsentStatus.WITHDRAWN, withdrawn_at=NOW - timedelta(days=1)),
            "CONSENT_WITHDRAWN",
        ),
        (
            _consent(status=ConsentStatus.RESTRICTED, restricted_at=NOW - timedelta(days=1)),
            "CONSENT_RESTRICTED",
        ),
        (_consent(status=ConsentStatus.EXPIRED), "CONSENT_EXPIRED"),
        (_consent(status=ConsentStatus.PENDING), "CONSENT_NOT_GRANTED"),
        (_consent(status=ConsentStatus.DENIED), "CONSENT_NOT_GRANTED"),
        (_consent(valid_from=NOW + timedelta(days=1)), "CONSENT_NOT_YET_VALID"),
        (
            _consent(valid_from=NOW - timedelta(days=7), valid_to=NOW - timedelta(days=1)),
            "CONSENT_EXPIRED",
        ),
        (_consent(scope_codes=("attendance",)), "CONSENT_SCOPE_DENIED"),
    ],
)
def test_non_granted_states_block_with_the_decision_reason(
    consent: Consent, expected_reason: str
) -> None:
    repository = StubRepository(ProcessingLookup((_purpose(),), (consent,)))
    decision = _service(repository).evaluate_processing(_payload(), _context())
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == expected_reason
    assert decision.policy_version == "consent_policy_v1"


def test_missing_consent_blocks_without_disclosing_more_than_not_found() -> None:
    repository = StubRepository(ProcessingLookup((_purpose(),), ()))
    decision = _service(repository).evaluate_processing(_payload(), _context())
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_NOT_FOUND"
    assert decision.policy_version == PROCESSING_GATE_POLICY_VERSION


def test_cross_school_lookup_stays_scoped_and_blocks_as_not_found() -> None:
    """A consent recorded under another school never leaks into this evaluation.

    The repository filters consents by the trusted school scope, so the other
    school's consent simply does not appear; with a global purpose active the
    decision is indistinguishable from no consent existing at all.
    """

    repository = StubRepository(ProcessingLookup((_purpose(school_id=None),), ()))
    service = ConsentApplicationService(cast(ConsentRepository, repository), clock=lambda: NOW)
    decision = service.evaluate_processing(
        _payload(),
        TrustedProcessingContext(
            school_id=OTHER_SCHOOL_ID,
            source_service="event-ingestion-service",
            gate_authorized=True,
        ),
    )
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_NOT_FOUND"
    assert repository.calls[0][0] == OTHER_SCHOOL_ID


def test_consent_to_a_superseded_purpose_version_does_not_cover_the_active_one() -> None:
    retired = _purpose(status=PurposeStatus.RETIRED)
    active_v2 = _purpose(purpose_id=PURPOSE_V2_ID, version=2)
    consent_to_v1 = _consent(purpose_id=PURPOSE_ID)
    repository = StubRepository(ProcessingLookup((retired, active_v2), (consent_to_v1,)))
    decision = _service(repository).evaluate_processing(_payload(), _context())
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_NOT_FOUND"


def test_two_active_purpose_versions_are_ambiguous_and_block() -> None:
    repository = StubRepository(
        ProcessingLookup(
            (_purpose(), _purpose(purpose_id=PURPOSE_V2_ID, version=2)),
            (_consent(),),
        )
    )
    decision = _service(repository).evaluate_processing(_payload(), _context())
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_PURPOSE_AMBIGUOUS"


def test_inactive_or_unknown_purpose_blocks() -> None:
    repository = StubRepository(ProcessingLookup((_purpose(status=PurposeStatus.RETIRED),), ()))
    decision = _service(repository).evaluate_processing(_payload(), _context())
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_PURPOSE_INACTIVE"


def test_unsupported_purpose_code_blocks_without_a_lookup() -> None:
    repository = StubRepository(ProcessingLookup((), ()))
    decision = _service(repository).evaluate_processing(_payload(purpose="violation"), _context())
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_PURPOSE_UNSUPPORTED"
    assert repository.calls == []


def test_unsupported_gate_policy_version_blocks() -> None:
    repository = StubRepository(ProcessingLookup((_purpose(),), (_consent(),)))
    decision = _service(repository).evaluate_processing(
        _payload(policy_version="consent_gate_v999"), _context()
    )
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_POLICY_VERSION_UNSUPPORTED"
    assert decision.policy_version == PROCESSING_GATE_POLICY_VERSION


@pytest.mark.parametrize("subject_ref", [None, "", "not-a-uuid", "   ", str(UUID(int=0))])
def test_unresolvable_subject_blocks_instead_of_raising(subject_ref: str | None) -> None:
    repository = StubRepository(ProcessingLookup((_purpose(),), ()))
    decision = _service(repository).evaluate_processing(
        _payload(subject_ref=subject_ref), _context()
    )
    assert decision.status is ProcessingConsentStatus.BLOCKED
    assert decision.reason_code == "CONSENT_SUBJECT_UNRESOLVED"


def test_purpose_not_requiring_biometric_consent_maps_to_not_required() -> None:
    repository = StubRepository(ProcessingLookup((_purpose(requires_biometric_consent=False),), ()))
    decision = _service(repository).evaluate_processing(_payload(subject_ref=None), _context())
    assert decision.status is ProcessingConsentStatus.NOT_REQUIRED
    assert decision.reason_code == "CONSENT_NOT_REQUIRED"
    assert decision.policy_version == PROCESSING_GATE_POLICY_VERSION


def test_repository_outage_escapes_as_unavailable_for_the_deferral_path() -> None:
    repository = StubRepository(ProcessingLookup((), ()), unavailable=True)
    with pytest.raises(ConsentError, match="CONSENT_UNAVAILABLE"):
        _service(repository).evaluate_processing(_payload(), _context())


def test_unauthorized_gate_context_is_denied() -> None:
    repository = StubRepository(ProcessingLookup((_purpose(),), (_consent(),)))
    with pytest.raises(ConsentError, match="CONSENT_AUTHORITY_DENIED"):
        _service(repository).evaluate_processing(_payload(), _context(authorized=False))
    assert repository.calls == []


def test_malformed_trusted_refs_are_input_errors() -> None:
    repository = StubRepository(ProcessingLookup((_purpose(),), (_consent(),)))
    payload = _payload()
    payload["tenant_ref"] = "bad ref with spaces"
    with pytest.raises(ConsentError, match="CONSENT_INPUT_INVALID"):
        _service(repository).evaluate_processing(payload, _context())
