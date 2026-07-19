from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from consent_service.config import ConsentConfigurationError, load_database_settings
from consent_service.domain.models import (
    AuthorityType,
    Consent,
    ConsentAuditIntent,
    ConsentChangeOutcome,
    ConsentDecision,
    ConsentDecisionCode,
    ConsentEvent,
    ConsentEventType,
    ConsentStatus,
    SubjectType,
)
from consent_service.logging import safe_change_log_fields, safe_decision_log_fields

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def test_config_requires_injected_postgresql_uri_without_echoing_it() -> None:
    with pytest.raises(ConsentConfigurationError, match="CONSENT_DATABASE_URI is required"):
        load_database_settings({"APP_ENV": "test"})

    scheme = "postgresql+psycopg"
    user_info = "synthetic-user" + ":" + "synthetic-private-value"
    secret_like = f"{scheme}://{user_info}@db.example.invalid/test_db"
    with pytest.raises(ConsentConfigurationError) as caught:
        load_database_settings({"APP_ENV": "production", "CONSENT_DATABASE_URI": secret_like})
    assert secret_like not in str(caught.value)
    assert "synthetic-private-value" not in repr(caught.value)


def test_safe_logs_exclude_tenant_subject_authority_and_resource_ids() -> None:
    consent = Consent(
        consent_id=_uuid(1),
        school_id=_uuid(2),
        subject_type=SubjectType.STUDENT,
        subject_id=_uuid(3),
        purpose_id=_uuid(4),
        authority_type=AuthorityType.GUARDIAN,
        authority_ref=_uuid(5),
        status=ConsentStatus.WITHDRAWN,
        scope_codes=("biometric",),
        valid_from=NOW,
        valid_to=None,
        withdrawn_at=NOW,
        restricted_at=None,
        policy_version="consent_v1",
        created_at=NOW,
        updated_at=NOW,
        row_version=3,
    )
    event = ConsentEvent(
        consent_event_id=_uuid(6),
        school_id=_uuid(2),
        consent_id=_uuid(1),
        event_type=ConsentEventType.WITHDRAWN,
        actor_id=_uuid(7),
        reason_code="AUTHORITY_WITHDRAWAL",
        request_id="req_0123456789abcdef",
        evidence_ref=None,
        idempotency_key="idem_test_value_01",
        request_fingerprint=bytes(32),
        resulting_version=3,
        occurred_at=NOW,
        recorded_at=NOW,
    )
    intent = ConsentAuditIntent(
        audit_intent_id=_uuid(8),
        consent_event_id=_uuid(6),
        source_event_id=_uuid(6),
        school_id=_uuid(2),
        actor_id=_uuid(7),
        action="CONSENT_WITHDRAWN",
        purpose_code="student_attendance",
        resource_id=_uuid(1),
        request_id="req_0123456789abcdef",
        result="success",
        reason_code="AUTHORITY_WITHDRAWAL",
        state_before="granted",
        state_after="withdrawn",
        policy_version="consent_v1",
        created_at=NOW,
    )
    fields = safe_change_log_fields(ConsentChangeOutcome(consent, event, intent, False), "change")
    decision_fields = safe_decision_log_fields(
        ConsentDecision(False, ConsentDecisionCode.WITHDRAWN, _uuid(1), 3)
    )
    combined = repr((fields, decision_fields))

    assert fields["action"] == "CONSENT_WITHDRAWN"
    assert decision_fields["reason_code"] == "CONSENT_WITHDRAWN"
    for forbidden in (_uuid(1), _uuid(2), _uuid(3), _uuid(5), _uuid(7)):
        assert str(forbidden) not in combined
