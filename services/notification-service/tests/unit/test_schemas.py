from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from notification_service.domain.errors import NotificationError
from notification_service.schemas.commands import parse_notification_intent

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_event_id": _uuid(1),
        "idempotency_key": "ntf_synthetic_000001",
        "tenant_id": _uuid(2),
        "school_id": _uuid(3),
        "subject_ref": _uuid(4),
        "resource_ref": _uuid(5),
        "content_class": "attendance_update",
        "template_code": "notification.attendance.generic",
        "template_version": 1,
        "source_state": "confirmed",
        "source_expires_at": NOW + timedelta(hours=2),
        "notification_expires_at": NOW + timedelta(hours=1),
        "recipient_refs": (_uuid(6),),
        "channels": ("in_app", "push", "email"),
        "request_id": "req_synthetic_0001",
        "correlation_id": "cor_synthetic_0001",
    }


def test_contract_is_strict_versioned_and_accepts_no_message_body() -> None:
    command = parse_notification_intent(payload())
    assert command.template_version == 1
    for forbidden in ("message_text", "signed_url", "device_token", "student_name"):
        invalid = payload()
        invalid[forbidden] = "synthetic-private-value"
        with pytest.raises(NotificationError, match="NOTIFICATION_REQUEST_INVALID"):
            parse_notification_intent(invalid)


def test_notification_cannot_outlive_its_source() -> None:
    invalid = payload()
    invalid["notification_expires_at"] = NOW + timedelta(hours=3)
    with pytest.raises(NotificationError, match="NOTIFICATION_REQUEST_INVALID"):
        parse_notification_intent(invalid)


def test_contract_does_not_coerce_version_or_boolean_like_values() -> None:
    for field in ("schema_version", "template_version"):
        invalid = payload()
        invalid[field] = "1"
        with pytest.raises(NotificationError, match="NOTIFICATION_REQUEST_INVALID"):
            parse_notification_intent(invalid)
