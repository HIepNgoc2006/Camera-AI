from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from consent_service.domain.errors import ConsentError
from consent_service.schemas.commands import (
    parse_evaluate_consent,
    parse_register_purpose,
    parse_request_consent,
    parse_transition_consent,
)

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)
SUBJECT_ID = UUID("00000000-0000-4000-8000-000000000001")
PURPOSE_ID = UUID("00000000-0000-4000-8000-000000000002")
AUTHORITY_ID = UUID("00000000-0000-4000-8000-000000000003")
CONSENT_ID = UUID("00000000-0000-4000-8000-000000000004")


def _request() -> dict[str, object]:
    return {
        "schema_version": 1,
        "purpose_id": str(PURPOSE_ID),
        "subject_type": "student",
        "subject_id": str(SUBJECT_ID),
        "authority_type": "guardian",
        "authority_ref": str(AUTHORITY_ID),
        "scope_codes": ["attendance", "biometric"],
        "policy_version": "consent_v1",
        "valid_from": NOW.isoformat(),
        "valid_to": (NOW + timedelta(days=10)).isoformat(),
        "request_id": "req_0123456789abcdef",
        "idempotency_key": "idem_test_value_01",
        "evidence_ref": "authority_record:00000000-0000-4000-8000-000000000005",
    }


def test_strict_commands_accept_only_minimized_versioned_values() -> None:
    purpose = parse_register_purpose(
        {
            "schema_version": 1,
            "code": "student_attendance",
            "description": "Synthetic attendance purpose.",
            "data_categories": ["attendance", "biometric"],
            "requires_biometric_consent": True,
            "status": "active",
            "version": 1,
            "valid_from": NOW.isoformat(),
        }
    )
    request = parse_request_consent(_request())
    transition = parse_transition_consent(
        {
            "schema_version": 1,
            "consent_id": str(CONSENT_ID),
            "target_status": "withdrawn",
            "expected_version": 2,
            "reason_code": "AUTHORITY_WITHDRAWAL",
            "request_id": "req_fedcba9876543210",
            "idempotency_key": "idem_test_value_02",
        }
    )
    evaluation = parse_evaluate_consent(
        {
            "schema_version": 1,
            "consent_id": str(CONSENT_ID),
            "purpose_id": str(PURPOSE_ID),
            "required_scope_codes": ["biometric"],
            "expected_version": 3,
        }
    )

    assert purpose.code == "student_attendance"
    assert len(request.fingerprint()) == 32
    assert transition.reason_code == "AUTHORITY_WITHDRAWAL"
    assert evaluation.required_scope_codes == ("biometric",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reason", "free text is forbidden"),
        ("evidence_ref", "https://private.example/object"),
        ("scope_codes", ["biometric", "biometric"]),
        ("scope_codes", ["unapproved_category"]),
        ("unknown_field", "unexpected"),
    ],
)
def test_request_rejects_unapproved_or_ambiguous_content(field: str, value: object) -> None:
    payload = _request()
    payload[field] = value
    with pytest.raises(ConsentError, match="CONSENT_INPUT_INVALID") as caught:
        parse_request_consent(payload)
    assert str(value) not in str(caught.value)


def test_parse_error_never_echoes_prohibited_payload() -> None:
    payload = _request()
    prohibited = "data:image/jpeg;base64,synthetic-secret-like-content"
    payload["evidence_ref"] = prohibited
    with pytest.raises(ConsentError) as caught:
        parse_request_consent(payload)
    assert prohibited not in str(caught.value)
