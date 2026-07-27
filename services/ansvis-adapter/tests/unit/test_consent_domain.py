"""Consent gate domain contract: purpose mapping, strict shapes, fan-out guard."""

from __future__ import annotations

from uuid import UUID

import pytest
from ansvis_adapter.domain.consent import (
    CONSENT_GATE_POLICY_VERSION,
    NOT_REQUIRED_DECISION,
    ConsentGateDecision,
    ConsentGateRequest,
    ConsentGateStatus,
    consent_purpose_for,
    fanout_permitted,
)
from ansvis_adapter.domain.models import EventType

SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000801")


def test_biometric_event_types_map_to_exactly_their_approved_purposes() -> None:
    assert consent_purpose_for(EventType.ATTENDANCE_FACE_OBSERVED) == "attendance"
    assert consent_purpose_for(EventType.TIMEKEEPING_FACE_OBSERVED) == "timekeeping"
    assert consent_purpose_for(EventType.EMOTION_OBSERVED) == "emotion"
    for event_type in (
        EventType.CAMERA_HEALTH_CHANGED,
        EventType.TASK_HEALTH_CHANGED,
        EventType.LITTERING_SUSPECTED,
        EventType.PPE_SUSPECTED,
        EventType.SMOKING_SUSPECTED,
        EventType.UNIFORM_SUSPECTED,
    ):
        assert consent_purpose_for(event_type) is None


def test_gate_request_rejects_unresolved_scope_and_unapproved_purpose() -> None:
    with pytest.raises(ValueError, match="school scope"):
        ConsentGateRequest(
            school_id=UUID(int=0),
            tenant_ref="tenant_test_0001",
            school_ref="school_test_0001",
            subject_ref=None,
            purpose_code="attendance",
            policy_version=CONSENT_GATE_POLICY_VERSION,
        )
    with pytest.raises(ValueError, match="approved purpose"):
        ConsentGateRequest(
            school_id=SCHOOL_ID,
            tenant_ref="tenant_test_0001",
            school_ref="school_test_0001",
            subject_ref=None,
            purpose_code="violation",
            policy_version=CONSENT_GATE_POLICY_VERSION,
        )
    with pytest.raises(ValueError, match="policy version"):
        ConsentGateRequest(
            school_id=SCHOOL_ID,
            tenant_ref="tenant_test_0001",
            school_ref="school_test_0001",
            subject_ref=None,
            purpose_code="attendance",
            policy_version="NOT_A_STABLE_CODE",
        )


def test_gate_decision_requires_stable_codes() -> None:
    with pytest.raises(ValueError, match="reason code"):
        ConsentGateDecision(
            status=ConsentGateStatus.BLOCKED,
            reason_code="free text with spaces",
            policy_version=CONSENT_GATE_POLICY_VERSION,
        )
    with pytest.raises(ValueError, match="policy version"):
        ConsentGateDecision(
            status=ConsentGateStatus.ALLOWED,
            reason_code="CONSENT_ALLOWED",
            policy_version="UPPER_NOT_ALLOWED",
        )
    assert NOT_REQUIRED_DECISION.status is ConsentGateStatus.NOT_REQUIRED


@pytest.mark.parametrize(
    ("payload", "permitted"),
    [
        ({"event_type": "camera.health.changed"}, True),
        ({"event_type": "violation.littering.suspected"}, True),
        (
            {"event_type": "attendance.face.observed", "consent_gate_status": "allowed"},
            True,
        ),
        (
            {"event_type": "insight.emotion.observed", "consent_gate_status": "not_required"},
            True,
        ),
        (
            {"event_type": "attendance.face.observed", "consent_gate_status": "blocked"},
            False,
        ),
        (
            {
                "event_type": "timekeeping.face.observed",
                "consent_gate_status": "not_evaluated",
            },
            False,
        ),
        ({"event_type": "attendance.face.observed"}, False),
        ({"event_type": "insight.emotion.observed", "consent_gate_status": 7}, False),
        ({"event_type": "made.up.type", "consent_gate_status": "allowed"}, False),
        ({"consent_gate_status": "allowed"}, False),
        ({"event_type": 42}, False),
        ({}, False),
    ],
)
def test_fanout_guard_fails_closed_for_unproven_payloads(
    payload: dict[str, object], permitted: bool
) -> None:
    assert fanout_permitted(payload) is permitted
