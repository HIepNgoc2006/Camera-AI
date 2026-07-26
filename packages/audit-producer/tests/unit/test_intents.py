"""Audit intent shape validation, payload minimization, and fail-closed recorder port."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from camera_ai_audit import (
    AuditIntent,
    AuditIntentInvalidError,
    AuditRecorderUnavailableError,
    IntentResult,
    UnavailableAuditIntentRecorder,
)
from camera_ai_audit.intents import AUDIT_EVENT_SCHEMA_VERSION

NOW = datetime(2026, 7, 26, 14, 0, tzinfo=UTC)
EVENT_ID = UUID("00000000-0000-4000-8000-000000000801")
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000802")


def denial_intent(**overrides: object) -> AuditIntent:
    values: dict[str, object] = {
        "source_service": "ansvis-adapter-service",
        "source_event_id": EVENT_ID,
        "action": "ANSVIS_SOURCE_AUTH_DENIED",
        "resource_type": "ansvis_source",
        "request_id": "req_test_0000000001",
        "result": IntentResult.DENIED,
        "reason_code": "EVENT_SOURCE_UNAUTHORIZED",
        "occurred_at": NOW,
    }
    values.update(overrides)
    return AuditIntent(**values)  # type: ignore[arg-type]


def test_payload_is_minimized_and_versioned() -> None:
    payload = denial_intent().publisher_payload()

    assert payload["event_schema_version"] == AUDIT_EVENT_SCHEMA_VERSION
    assert payload["source_service"] == "ansvis-adapter-service"
    assert payload["action"] == "ANSVIS_SOURCE_AUTH_DENIED"
    assert payload["result"] == "denied"
    assert "changes" not in payload
    assert "school_id" not in payload  # trusted context, never publisher payload
    assert "actor_id" not in payload


def test_changes_render_only_bounded_structures() -> None:
    intent = denial_intent(
        source_service="event-ingestion-service",
        action="EVENT_PROCESSING_DEAD_LETTERED",
        resource_type="event",
        result=IntentResult.FAILED,
        reason_code="EVENT_OUTBOX_PUBLISH_FAILED",
        resource_id=EVENT_ID,
        school_id=SCHOOL_ID,
        reference_ids=(("event_id", EVENT_ID),),
        count_summary=(("attempt_count", 5),),
        policy_versions=(("event_contract", "normalized_outbox_v1"),),
    )

    changes = intent.publisher_payload()["changes"]
    assert isinstance(changes, dict)
    assert changes["schema_version"] == "audit_changes_v1"
    assert changes["reference_ids"] == {"event_id": str(EVENT_ID)}
    assert changes["count_summary"] == {"attempt_count": 5}
    assert changes["policy_versions"] == {"event_contract": "normalized_outbox_v1"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_service": "Bad Service"},
        {"action": "lowercase_action"},
        {"request_id": "not-a-request-id"},
        {"reason_code": None},  # denied requires a reason
        {"reason_code": "lower_reason"},
        {"resource_type": "UPPER"},
        {"occurred_at": NOW.replace(tzinfo=None)},
        {"source_event_id": UUID(int=0)},
        {"resource_id": EVENT_ID, "resource_ref": "also-a-ref"},
        {"correlation_id": "wrong_prefix_0000000001"},
        {"count_summary": (("attempt_count", -1),)},
        {"reference_ids": (("event_id", UUID(int=0)),)},
    ],
)
def test_invalid_shapes_fail_closed_without_echoing_values(overrides: dict[str, object]) -> None:
    with pytest.raises(AuditIntentInvalidError) as excinfo:
        denial_intent(**overrides)
    assert str(excinfo.value) == "AUDIT_INTENT_INVALID"


def test_unavailable_recorder_refuses_with_stable_code() -> None:
    with pytest.raises(AuditRecorderUnavailableError, match="AUDIT_RECORDER_UNAVAILABLE"):
        UnavailableAuditIntentRecorder().record(denial_intent())
