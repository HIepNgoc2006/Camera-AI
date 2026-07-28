from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    Channel,
    ConsentDecision,
    ContentClass,
    NotificationCommand,
    RecipientAuthorization,
    TrustedSourceContext,
)
from notification_service.domain.policies import (
    authorize_recipient,
    authorize_source,
    can_cancel,
    render_generic,
)

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def command() -> NotificationCommand:
    return NotificationCommand(
        source_event_id=_uuid(1),
        idempotency_key="ntf_synthetic_000001",
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        subject_ref=_uuid(4),
        resource_ref=_uuid(5),
        content_class=ContentClass.ATTENDANCE_UPDATE,
        template_code="notification.attendance.generic",
        template_version=1,
        source_state="confirmed",
        source_expires_at=NOW + timedelta(hours=2),
        notification_expires_at=NOW + timedelta(hours=1),
        recipient_refs=(_uuid(6),),
        channels=(Channel.IN_APP, Channel.PUSH, Channel.EMAIL),
        request_id="req_synthetic_0001",
        correlation_id="cor_synthetic_0001",
    )


def source_context() -> TrustedSourceContext:
    return TrustedSourceContext(
        source_service="attendance-service",
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        trusted_identity=True,
        permission_codes=frozenset({"service.notification.request"}),
        delegation_authorized=True,
        runtime_approvals_complete=True,
        policy_version="notification_privacy_policy_v1",
    )


def authorization() -> RecipientAuthorization:
    return RecipientAuthorization(
        recipient_ref=_uuid(6),
        tenant_id=_uuid(2),
        school_id=_uuid(3),
        recipient_role="parent_guardian",
        relationship_code="active_linked_child",
        permission_code="notification.attendance.receive",
        purpose_code="attendance_notification",
        recipient_active=True,
        relationship_current=True,
        permission_current=True,
        purpose_active=True,
        consent_decision=ConsentDecision.ALLOWED,
        source_current=True,
        endpoint_active=True,
        endpoint_verified=True,
        endpoint_owned=True,
        channel_preference_enabled=True,
        dependencies_available=True,
    )


def test_source_and_recipient_require_exact_current_authority() -> None:
    authorize_source(command(), source_context())
    permission, purpose = authorize_recipient(command(), authorization(), Channel.PUSH, now=NOW)
    assert permission == "notification.attendance.receive"
    assert purpose == "attendance_notification"

    denied = replace(authorization(), consent_decision=ConsentDecision.BLOCKED)
    with pytest.raises(NotificationError, match="NOTIFICATION_CONSENT_DENIED"):
        authorize_recipient(command(), denied, Channel.PUSH, now=NOW)


def test_rendered_content_is_generic_and_channel_minimized() -> None:
    for channel in Channel:
        rendered = render_generic(command(), channel, "opaque-notification", created_at=NOW)
        content = dict(rendered.fields)
        assert "generic_body_code" in content
        assert not {
            "student_name",
            "attendance_status",
            "signed_url",
            "device_token",
            "message_text",
        } & set(content)
        if channel is not Channel.IN_APP:
            assert "opaque_resource_ref" not in content


def test_cancellation_triggers_are_closed() -> None:
    assert can_cancel("consent_withdrawn")
    assert can_cancel("endpoint_revoked")
    assert not can_cancel("manual_convenience")


@pytest.mark.parametrize(
    ("context", "code"),
    [
        (replace(source_context(), trusted_identity=False), "NOTIFICATION_SOURCE_SERVICE_DENIED"),
        (
            replace(source_context(), permission_codes=frozenset()),
            "NOTIFICATION_SOURCE_SERVICE_DENIED",
        ),
        (
            replace(source_context(), delegation_authorized=False),
            "NOTIFICATION_DELEGATION_REQUIRED",
        ),
        (replace(source_context(), tenant_id=_uuid(90)), "NOTIFICATION_NOT_FOUND"),
        (replace(source_context(), school_id=_uuid(91)), "NOTIFICATION_NOT_FOUND"),
        (
            replace(source_context(), runtime_approvals_complete=False),
            "NOTIFICATION_POLICY_INACTIVE",
        ),
        (
            replace(source_context(), policy_version="notification_privacy_policy_v2"),
            "NOTIFICATION_POLICY_INACTIVE",
        ),
    ],
)
def test_source_boundary_denies_scope_delegation_and_inactive_policy(
    context: TrustedSourceContext,
    code: str,
) -> None:
    with pytest.raises(NotificationError, match=code):
        authorize_source(command(), context)


@pytest.mark.parametrize(
    ("decision", "channel", "code"),
    [
        (
            replace(authorization(), recipient_ref=_uuid(90)),
            Channel.IN_APP,
            "NOTIFICATION_RECIPIENT_SCOPE_DENIED",
        ),
        (
            replace(authorization(), tenant_id=_uuid(90)),
            Channel.IN_APP,
            "NOTIFICATION_RECIPIENT_SCOPE_DENIED",
        ),
        (
            replace(authorization(), school_id=_uuid(90)),
            Channel.IN_APP,
            "NOTIFICATION_RECIPIENT_SCOPE_DENIED",
        ),
        (
            replace(authorization(), relationship_current=False),
            Channel.IN_APP,
            "NOTIFICATION_RECIPIENT_SCOPE_DENIED",
        ),
        (
            replace(authorization(), permission_current=False),
            Channel.IN_APP,
            "NOTIFICATION_PERMISSION_DENIED",
        ),
        (
            replace(authorization(), purpose_active=False),
            Channel.IN_APP,
            "NOTIFICATION_PURPOSE_DENIED",
        ),
        (
            replace(authorization(), consent_decision=ConsentDecision.BLOCKED),
            Channel.IN_APP,
            "NOTIFICATION_CONSENT_DENIED",
        ),
        (
            replace(authorization(), source_current=False),
            Channel.IN_APP,
            "NOTIFICATION_SOURCE_NOT_ELIGIBLE",
        ),
        (
            replace(authorization(), endpoint_owned=False),
            Channel.PUSH,
            "NOTIFICATION_ENDPOINT_DENIED",
        ),
        (
            replace(authorization(), dependencies_available=False),
            Channel.IN_APP,
            "NOTIFICATION_DEPENDENCY_UNAVAILABLE",
        ),
    ],
)
def test_recipient_boundary_denies_stale_or_cross_scope_state(
    decision: RecipientAuthorization,
    channel: Channel,
    code: str,
) -> None:
    with pytest.raises(NotificationError, match=code):
        authorize_recipient(command(), decision, channel, now=NOW)


def test_template_and_expiry_cannot_be_bypassed() -> None:
    with pytest.raises(NotificationError, match="NOTIFICATION_SOURCE_NOT_ELIGIBLE"):
        authorize_recipient(
            replace(command(), template_code="notification.attendance.unapproved"),
            authorization(),
            Channel.IN_APP,
            now=NOW,
        )
    with pytest.raises(NotificationError, match="NOTIFICATION_EXPIRED"):
        authorize_recipient(
            command(),
            authorization(),
            Channel.IN_APP,
            now=NOW + timedelta(hours=1),
        )
