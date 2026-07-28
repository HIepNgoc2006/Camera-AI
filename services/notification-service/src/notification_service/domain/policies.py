"""Version-pinned content, recipient, retry and cancellation policy."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Final

from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    Channel,
    ConsentDecision,
    ContentClass,
    NotificationCommand,
    RecipientAuthorization,
    RenderedContent,
    TrustedSourceContext,
)

MAX_ATTEMPTS: Final = 5
BASE_BACKOFF_SECONDS: Final = 2
MAX_INFLIGHT_RETRIES: Final = 5_000

CONTENT_RULES = MappingProxyType(
    {
        ContentClass.ATTENDANCE_UPDATE: (
            "notification.attendance.generic",
            "notification.attendance.receive",
            "attendance_notification",
            frozenset({"confirmed", "corrected"}),
            frozenset({"parent_guardian", "teacher", "bgh"}),
        ),
        ContentClass.TIMEKEEPING_UPDATE: (
            "notification.timekeeping.generic",
            "notification.timekeeping.receive",
            "timekeeping_notification",
            frozenset({"confirmed", "corrected"}),
            frozenset({"staff_self", "hr_officer", "bgh"}),
        ),
        ContentClass.VIOLATION_UPDATE: (
            "notification.violation.generic",
            "notification.violation.receive",
            "violation_notification",
            frozenset({"confirmed", "corrected"}),
            frozenset({"parent_guardian", "teacher", "bgh", "kitchen_manager"}),
        ),
        ContentClass.CORRECTION_UPDATE: (
            "notification.correction.generic",
            "notification.correction.receive",
            "correction_notification",
            frozenset({"corrected"}),
            frozenset({"parent_guardian", "teacher", "staff_self", "hr_officer", "bgh"}),
        ),
        ContentClass.PRIVACY_ACTION: (
            "notification.privacy_action.generic",
            "notification.privacy.receive",
            "privacy_action_notification",
            frozenset({"action_required"}),
            frozenset({"parent_guardian", "staff_self", "privacy_officer"}),
        ),
        ContentClass.OPERATIONAL_ALERT: (
            "notification.operational_alert.generic",
            "notification.operations.receive",
            "operations_notification",
            frozenset({"active_alert", "resolved_alert"}),
            frozenset({"bgh", "school_admin", "system_admin", "technical_operator"}),
        ),
    }
)

RELATIONSHIPS = MappingProxyType(
    {
        "parent_guardian": frozenset({"active_linked_child"}),
        "teacher": frozenset({"assigned_class_schedule_task", "assigned_homeroom"}),
        "staff_self": frozenset({"own_staff_record"}),
        "hr_officer": frozenset({"assigned_hr_unit"}),
        "bgh": frozenset({"assigned_school"}),
        "kitchen_manager": frozenset({"assigned_kitchen_zone_shift"}),
        "privacy_officer": frozenset({"approved_privacy_case"}),
        "school_admin": frozenset({"assigned_school"}),
        "system_admin": frozenset({"system_operations"}),
        "technical_operator": frozenset({"system_operations"}),
    }
)


def authorize_source(command: NotificationCommand, context: TrustedSourceContext) -> None:
    if (
        not context.trusted_identity
        or "service.notification.request" not in context.permission_codes
    ):
        raise NotificationError("NOTIFICATION_SOURCE_SERVICE_DENIED")
    if not context.delegation_authorized:
        raise NotificationError("NOTIFICATION_DELEGATION_REQUIRED")
    if command.tenant_id != context.tenant_id or command.school_id != context.school_id:
        raise NotificationError("NOTIFICATION_NOT_FOUND")
    if (
        not context.runtime_approvals_complete
        or context.policy_version != "notification_privacy_policy_v1"
    ):
        raise NotificationError("NOTIFICATION_POLICY_INACTIVE")


def authorize_recipient(
    command: NotificationCommand,
    authorization: RecipientAuthorization,
    channel: Channel,
    *,
    now: datetime,
) -> tuple[str, str]:
    if not authorization.dependencies_available:
        raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE")
    if (
        authorization.recipient_ref not in command.recipient_refs
        or authorization.tenant_id != command.tenant_id
        or authorization.school_id != command.school_id
    ):
        raise NotificationError("NOTIFICATION_RECIPIENT_SCOPE_DENIED")
    template, permission, purpose, source_states, roles = CONTENT_RULES[command.content_class]
    relationships = RELATIONSHIPS.get(authorization.recipient_role, frozenset())
    if (
        not authorization.recipient_active
        or authorization.recipient_role not in roles
        or authorization.relationship_code not in relationships
        or not authorization.relationship_current
    ):
        raise NotificationError("NOTIFICATION_RECIPIENT_SCOPE_DENIED")
    if not authorization.permission_current or authorization.permission_code != permission:
        raise NotificationError("NOTIFICATION_PERMISSION_DENIED")
    if not authorization.purpose_active or authorization.purpose_code != purpose:
        raise NotificationError("NOTIFICATION_PURPOSE_DENIED")
    if authorization.consent_decision not in {
        ConsentDecision.ALLOWED,
        ConsentDecision.NOT_REQUIRED,
    }:
        raise NotificationError("NOTIFICATION_CONSENT_DENIED")
    if (
        command.template_code != template
        or command.source_state not in source_states
        or not authorization.source_current
    ):
        raise NotificationError("NOTIFICATION_SOURCE_NOT_ELIGIBLE")
    if now >= command.notification_expires_at or now >= command.source_expires_at:
        raise NotificationError("NOTIFICATION_EXPIRED")
    if channel is not Channel.IN_APP and (
        not authorization.endpoint_active
        or not authorization.endpoint_verified
        or not authorization.endpoint_owned
        or not authorization.channel_preference_enabled
    ):
        raise NotificationError("NOTIFICATION_ENDPOINT_DENIED")
    return permission, purpose


def render_generic(
    command: NotificationCommand,
    channel: Channel,
    notification_ref: str,
    *,
    created_at: datetime,
) -> RenderedContent:
    common: dict[str, str | int | bool] = {
        "template_code": command.template_code,
        "template_version": command.template_version,
        "generic_body_code": f"{command.template_code}.body",
        "opaque_notification_ref": notification_ref,
        "expires_at": command.notification_expires_at.isoformat(),
    }
    if channel is Channel.IN_APP:
        common.update(
            {
                "generic_title_code": f"{command.template_code}.title",
                "opaque_resource_ref": str(command.resource_ref),
                "created_at": created_at.isoformat(),
                "action_available": True,
            }
        )
    elif channel is Channel.PUSH:
        common.update(
            {
                "generic_title_code": f"{command.template_code}.title",
                "allowlisted_route_code": "notification_inbox",
            }
        )
    else:
        common.update(
            {
                "generic_subject_code": f"{command.template_code}.subject",
                "allowlisted_route_code": "notification_inbox",
            }
        )
    return RenderedContent(channel=channel, fields=common)


def retry_schedule(
    *,
    attempt_count: int,
    now: datetime,
    expires_at: datetime,
    retry_backlog: int,
    jitter: Callable[[int], int],
) -> datetime | None:
    next_attempt = attempt_count + 1
    if next_attempt >= MAX_ATTEMPTS:
        return None
    if retry_backlog < 0 or retry_backlog >= MAX_INFLIGHT_RETRIES:
        raise NotificationError("NOTIFICATION_RETRY_DENIED")
    delay = BASE_BACKOFF_SECONDS * (2 ** (next_attempt - 1))
    jitter_max = max(1, delay // 5)
    jitter_seconds = jitter(jitter_max)
    if not 0 <= jitter_seconds <= jitter_max:
        raise NotificationError("NOTIFICATION_RETRY_DENIED")
    scheduled = now + timedelta(seconds=delay + jitter_seconds)
    if scheduled >= expires_at:
        return None
    return scheduled


def can_cancel(trigger: str) -> bool:
    return trigger in {
        "consent_withdrawn",
        "permission_revoked",
        "relationship_revoked",
        "recipient_deactivated",
        "endpoint_revoked",
        "source_rejected",
        "source_expired",
        "purpose_ended",
        "policy_superseded",
    }
