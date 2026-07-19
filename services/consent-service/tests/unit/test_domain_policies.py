from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    AuthorityType,
    Consent,
    ConsentDecision,
    ConsentDecisionCode,
    ConsentStatus,
    Purpose,
    PurposeStatus,
    SubjectType,
    TrustedEvaluationContext,
    transition_consent,
)
from consent_service.domain.policies import evaluate_consent

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000001")
OTHER_SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000002")
SUBJECT_ID = UUID("00000000-0000-4000-8000-000000000003")
OTHER_SUBJECT_ID = UUID("00000000-0000-4000-8000-000000000004")
PURPOSE_ID = UUID("00000000-0000-4000-8000-000000000005")
OTHER_PURPOSE_ID = UUID("00000000-0000-4000-8000-000000000006")
CONSENT_ID = UUID("00000000-0000-4000-8000-000000000007")
AUTHORITY_ID = UUID("00000000-0000-4000-8000-000000000008")


def _purpose() -> Purpose:
    return Purpose(
        purpose_id=PURPOSE_ID,
        school_id=SCHOOL_ID,
        code="student_attendance",
        description="Synthetic purpose for attendance consent tests.",
        data_categories=("attendance", "biometric"),
        requires_biometric_consent=True,
        status=PurposeStatus.ACTIVE,
        version=1,
        valid_from=NOW - timedelta(days=1),
        valid_to=NOW + timedelta(days=30),
        created_at=NOW - timedelta(days=1),
    )


def _consent() -> Consent:
    return Consent(
        consent_id=CONSENT_ID,
        school_id=SCHOOL_ID,
        subject_type=SubjectType.STUDENT,
        subject_id=SUBJECT_ID,
        purpose_id=PURPOSE_ID,
        authority_type=AuthorityType.GUARDIAN,
        authority_ref=AUTHORITY_ID,
        status=ConsentStatus.GRANTED,
        scope_codes=("attendance", "biometric"),
        valid_from=NOW - timedelta(hours=1),
        valid_to=NOW + timedelta(days=1),
        withdrawn_at=None,
        restricted_at=None,
        policy_version="consent_v1",
        created_at=NOW - timedelta(hours=2),
        updated_at=NOW - timedelta(hours=1),
        row_version=2,
    )


def _context() -> TrustedEvaluationContext:
    return TrustedEvaluationContext(
        school_id=SCHOOL_ID,
        subject_type=SubjectType.STUDENT,
        subject_id=SUBJECT_ID,
        relationship_verified=True,
    )


def _evaluate(
    consent: Consent | None = None,
    purpose: Purpose | None = None,
    *,
    context: TrustedEvaluationContext | None = None,
    expected_purpose_id: UUID = PURPOSE_ID,
    required_scope_codes: tuple[str, ...] = ("biometric",),
    expected_version: int | None = 2,
    evaluated_at: datetime = NOW,
) -> ConsentDecision:
    return evaluate_consent(
        _consent() if consent is None else consent,
        _purpose() if purpose is None else purpose,
        context=_context() if context is None else context,
        expected_purpose_id=expected_purpose_id,
        required_scope_codes=required_scope_codes,
        expected_version=expected_version,
        evaluated_at=evaluated_at,
    )


def test_exact_purpose_scope_and_relationship_are_required() -> None:
    allowed = _evaluate()
    assert allowed.allowed is True
    assert allowed.reason_code is ConsentDecisionCode.ALLOWED

    wrong_subject = replace(_context(), subject_id=OTHER_SUBJECT_ID)
    assert _evaluate(context=wrong_subject).reason_code is ConsentDecisionCode.SUBJECT_MISMATCH
    assert (
        _evaluate(expected_purpose_id=OTHER_PURPOSE_ID).reason_code
        is ConsentDecisionCode.PURPOSE_MISMATCH
    )
    assert (
        _evaluate(context=replace(_context(), relationship_verified=False)).reason_code
        is ConsentDecisionCode.AUTHORITY_DENIED
    )
    assert (
        _evaluate(required_scope_codes=("evidence",)).reason_code
        is ConsentDecisionCode.SCOPE_DENIED
    )
    assert _evaluate(expected_version=1).reason_code is ConsentDecisionCode.STALE_VERSION


@pytest.mark.parametrize(
    ("consent", "purpose", "instant", "reason"),
    [
        (
            replace(_consent(), status=ConsentStatus.PENDING, valid_from=None),
            _purpose(),
            NOW,
            "CONSENT_NOT_GRANTED",
        ),
        (
            replace(_consent(), status=ConsentStatus.WITHDRAWN, withdrawn_at=NOW),
            _purpose(),
            NOW,
            "CONSENT_WITHDRAWN",
        ),
        (
            replace(_consent(), status=ConsentStatus.RESTRICTED, restricted_at=NOW),
            _purpose(),
            NOW,
            "CONSENT_RESTRICTED",
        ),
        (replace(_consent(), status=ConsentStatus.EXPIRED), _purpose(), NOW, "CONSENT_EXPIRED"),
        (
            replace(_consent(), valid_from=NOW + timedelta(minutes=1)),
            _purpose(),
            NOW,
            "CONSENT_NOT_YET_VALID",
        ),
        (
            replace(_consent(), valid_to=NOW),
            _purpose(),
            NOW,
            "CONSENT_EXPIRED",
        ),
        (
            _consent(),
            replace(_purpose(), status=PurposeStatus.RETIRED),
            NOW,
            "CONSENT_PURPOSE_INACTIVE",
        ),
    ],
)
def test_status_and_time_denial_matrix(
    consent: Consent,
    purpose: Purpose,
    instant: datetime,
    reason: str,
) -> None:
    decision = _evaluate(consent, purpose, evaluated_at=instant)
    assert decision.allowed is False
    assert decision.reason_code.value == reason


def test_missing_and_cross_tenant_lookup_fail_closed_without_identifiers() -> None:
    missing = evaluate_consent(
        None,
        None,
        context=replace(_context(), school_id=OTHER_SCHOOL_ID),
        expected_purpose_id=PURPOSE_ID,
        required_scope_codes=("biometric",),
        expected_version=None,
        evaluated_at=NOW,
    )
    assert missing.reason_code is ConsentDecisionCode.NOT_FOUND
    assert missing.consent_id is None

    mismatched_record = _evaluate(
        consent=replace(_consent(), school_id=OTHER_SCHOOL_ID),
    )
    assert mismatched_record.reason_code is ConsentDecisionCode.NOT_FOUND
    assert mismatched_record.consent_id is None


def test_state_machine_makes_withdrawal_immediate_and_terminal() -> None:
    withdrawn = transition_consent(_consent(), ConsentStatus.WITHDRAWN, changed_at=NOW)
    assert withdrawn.status is ConsentStatus.WITHDRAWN
    assert withdrawn.withdrawn_at == NOW
    assert withdrawn.row_version == 3

    with pytest.raises(ConsentError, match="CONSENT_TRANSITION_DENIED"):
        transition_consent(withdrawn, ConsentStatus.GRANTED, changed_at=NOW + timedelta(seconds=1))
