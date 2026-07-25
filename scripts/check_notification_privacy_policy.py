from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = Path("packages/notification-privacy-policy/notification-privacy-policy-v1.json")
FIXTURE_PATH = Path(
    "packages/test-fixtures/notification-privacy/notification-privacy-policy-cases.synthetic.json"
)

NOTIFICATION_POLICY_INVALID = "NOTIFICATION_POLICY_INVALID"
NOTIFICATION_FIXTURE_INVALID = "NOTIFICATION_FIXTURE_INVALID"

EXPECTED_OPERATIONS = {"dispatch", "retry", "dead_letter", "open", "cancel"}

EXPECTED_CHANNELS: dict[str, dict[str, object]] = {
    "in_app": {
        "required_fields": {
            "template_code",
            "template_version",
            "generic_title_code",
            "generic_body_code",
            "opaque_notification_ref",
            "opaque_resource_ref",
            "created_at",
            "expires_at",
        },
        "allowed_fields": {
            "template_code",
            "template_version",
            "generic_title_code",
            "generic_body_code",
            "category_code",
            "opaque_notification_ref",
            "opaque_resource_ref",
            "created_at",
            "expires_at",
            "action_available",
        },
        "endpoint_requirement": "authenticated_in_app_inbox",
        "preview_rule": "generic_codes_only",
    },
    "push": {
        "required_fields": {
            "template_code",
            "template_version",
            "generic_title_code",
            "generic_body_code",
            "opaque_notification_ref",
            "allowlisted_route_code",
            "expires_at",
        },
        "allowed_fields": {
            "template_code",
            "template_version",
            "generic_title_code",
            "generic_body_code",
            "category_code",
            "opaque_notification_ref",
            "allowlisted_route_code",
            "expires_at",
        },
        "endpoint_requirement": "active_verified_owned_encrypted_device_endpoint",
        "preview_rule": "generic_text_and_opaque_notification_ref_only",
    },
    "email": {
        "required_fields": {
            "template_code",
            "template_version",
            "generic_subject_code",
            "generic_body_code",
            "opaque_notification_ref",
            "allowlisted_route_code",
            "expires_at",
        },
        "allowed_fields": {
            "template_code",
            "template_version",
            "generic_subject_code",
            "generic_body_code",
            "category_code",
            "opaque_notification_ref",
            "allowlisted_route_code",
            "expires_at",
        },
        "endpoint_requirement": "active_verified_owned_encrypted_email_endpoint",
        "preview_rule": "generic_text_and_opaque_notification_ref_only",
    },
}

EXPECTED_CONTENT_CLASSES: dict[str, dict[str, object]] = {
    "attendance_update": {
        "template_code": "notification.attendance.generic",
        "template_version": 1,
        "permission_code": "notification.attendance.receive",
        "purpose_code": "attendance_notification",
        "allowed_channels": {"in_app", "push", "email"},
        "allowed_source_states": {"confirmed", "corrected"},
        "candidate_recipient_roles": {"parent_guardian", "teacher", "bgh"},
    },
    "timekeeping_update": {
        "template_code": "notification.timekeeping.generic",
        "template_version": 1,
        "permission_code": "notification.timekeeping.receive",
        "purpose_code": "timekeeping_notification",
        "allowed_channels": {"in_app", "push", "email"},
        "allowed_source_states": {"confirmed", "corrected"},
        "candidate_recipient_roles": {"staff_self", "hr_officer", "bgh"},
    },
    "violation_update": {
        "template_code": "notification.violation.generic",
        "template_version": 1,
        "permission_code": "notification.violation.receive",
        "purpose_code": "violation_notification",
        "allowed_channels": {"in_app", "push", "email"},
        "allowed_source_states": {"confirmed", "corrected"},
        "candidate_recipient_roles": {
            "parent_guardian",
            "teacher",
            "bgh",
            "kitchen_manager",
        },
    },
    "correction_update": {
        "template_code": "notification.correction.generic",
        "template_version": 1,
        "permission_code": "notification.correction.receive",
        "purpose_code": "correction_notification",
        "allowed_channels": {"in_app", "push", "email"},
        "allowed_source_states": {"corrected"},
        "candidate_recipient_roles": {
            "parent_guardian",
            "teacher",
            "staff_self",
            "hr_officer",
            "bgh",
        },
    },
    "privacy_action": {
        "template_code": "notification.privacy_action.generic",
        "template_version": 1,
        "permission_code": "notification.privacy.receive",
        "purpose_code": "privacy_action_notification",
        "allowed_channels": {"in_app", "push", "email"},
        "allowed_source_states": {"action_required"},
        "candidate_recipient_roles": {
            "parent_guardian",
            "staff_self",
            "privacy_officer",
        },
    },
    "operational_alert": {
        "template_code": "notification.operational_alert.generic",
        "template_version": 1,
        "permission_code": "notification.operations.receive",
        "purpose_code": "operations_notification",
        "allowed_channels": {"in_app", "push", "email"},
        "allowed_source_states": {"active_alert", "resolved_alert"},
        "candidate_recipient_roles": {
            "bgh",
            "school_admin",
            "system_admin",
            "technical_operator",
        },
    },
}

EXPECTED_RECIPIENT_ROLES: dict[str, dict[str, set[str]]] = {
    "parent_guardian": {
        "relationships": {"active_linked_child"},
        "content_classes": {
            "attendance_update",
            "violation_update",
            "correction_update",
            "privacy_action",
        },
        "channels": {"in_app", "push", "email"},
    },
    "teacher": {
        "relationships": {"assigned_class_schedule_task", "assigned_homeroom"},
        "content_classes": {
            "attendance_update",
            "violation_update",
            "correction_update",
        },
        "channels": {"in_app", "push", "email"},
    },
    "staff_self": {
        "relationships": {"own_staff_record"},
        "content_classes": {
            "timekeeping_update",
            "correction_update",
            "privacy_action",
        },
        "channels": {"in_app", "push", "email"},
    },
    "hr_officer": {
        "relationships": {"assigned_hr_unit"},
        "content_classes": {"timekeeping_update", "correction_update"},
        "channels": {"in_app", "push", "email"},
    },
    "bgh": {
        "relationships": {"assigned_school"},
        "content_classes": {
            "attendance_update",
            "timekeeping_update",
            "violation_update",
            "correction_update",
            "operational_alert",
        },
        "channels": {"in_app", "push", "email"},
    },
    "kitchen_manager": {
        "relationships": {"assigned_kitchen_zone_shift"},
        "content_classes": {"violation_update"},
        "channels": {"in_app", "push", "email"},
    },
    "privacy_officer": {
        "relationships": {"approved_privacy_case"},
        "content_classes": {"privacy_action"},
        "channels": {"in_app", "email"},
    },
    "school_admin": {
        "relationships": {"assigned_school"},
        "content_classes": {"operational_alert"},
        "channels": {"in_app", "push", "email"},
    },
    "system_admin": {
        "relationships": {"system_operations"},
        "content_classes": {"operational_alert"},
        "channels": {"in_app", "push", "email"},
    },
    "technical_operator": {
        "relationships": {"system_operations"},
        "content_classes": {"operational_alert"},
        "channels": {"in_app", "push", "email"},
    },
    "auditor": {
        "relationships": set(),
        "content_classes": set(),
        "channels": set(),
    },
}

EXPECTED_PROHIBITED_FIELDS = {
    "student_name",
    "staff_name",
    "guardian_name",
    "email_address",
    "phone_number",
    "student_code",
    "class_name",
    "attendance_status",
    "attendance_time",
    "timekeeping_status",
    "timekeeping_time",
    "violation_type",
    "violation_detail",
    "disciplinary_outcome",
    "emotion_label",
    "emotion_confidence",
    "health_inference",
    "consent_state",
    "face_image",
    "image_base64",
    "media_url",
    "signed_url",
    "bucket_name",
    "object_key",
    "provider_locator",
    "camera_id",
    "zone_name",
    "raw_ansvis_payload",
    "face_embedding",
    "device_token",
    "access_token",
    "refresh_token",
    "credential",
    "free_form_note",
}

EXPECTED_DEAD_LETTER_FIELDS = {
    "opaque_notification_ref",
    "opaque_recipient_ref",
    "opaque_resource_ref",
    "channel",
    "template_version",
    "policy_version",
    "purpose_code",
    "attempt_count",
    "next_attempt_at",
    "expires_at",
    "correlation_id",
    "stable_failure_category",
}

EXPECTED_CANCELLATION_TRIGGERS = {
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

EXPECTED_REASON_CODES = {
    "dispatch_allowed": "NOTIFICATION_DISPATCH_ALLOWED",
    "retry_allowed": "NOTIFICATION_RETRY_ALLOWED",
    "dead_letter_allowed": "NOTIFICATION_DEAD_LETTER_ALLOWED",
    "open_allowed": "NOTIFICATION_OPEN_ALLOWED",
    "cancellation_allowed": "NOTIFICATION_CANCELLATION_ALLOWED",
    "service_identity_denied": "NOTIFICATION_SERVICE_IDENTITY_DENIED",
    "source_service_denied": "NOTIFICATION_SOURCE_SERVICE_DENIED",
    "delegation_required": "NOTIFICATION_DELEGATION_REQUIRED",
    "provider_adapter_denied": "NOTIFICATION_PROVIDER_ADAPTER_DENIED",
    "recipient_unauthenticated": "NOTIFICATION_RECIPIENT_UNAUTHENTICATED",
    "recipient_inactive": "NOTIFICATION_RECIPIENT_INACTIVE",
    "recipient_scope_denied": "NOTIFICATION_RECIPIENT_SCOPE_DENIED",
    "permission_denied": "NOTIFICATION_PERMISSION_DENIED",
    "purpose_denied": "NOTIFICATION_PURPOSE_DENIED",
    "consent_denied": "NOTIFICATION_CONSENT_DENIED",
    "policy_inactive": "NOTIFICATION_POLICY_INACTIVE",
    "channel_denied": "NOTIFICATION_CHANNEL_DENIED",
    "content_denied": "NOTIFICATION_CONTENT_DENIED",
    "source_not_eligible": "NOTIFICATION_SOURCE_NOT_ELIGIBLE",
    "expired": "NOTIFICATION_EXPIRED",
    "cancelled": "NOTIFICATION_CANCELLED",
    "endpoint_denied": "NOTIFICATION_ENDPOINT_DENIED",
    "duplicate_suppressed": "NOTIFICATION_DUPLICATE_SUPPRESSED",
    "retry_denied": "NOTIFICATION_RETRY_DENIED",
    "dead_letter_payload_invalid": "NOTIFICATION_DEAD_LETTER_PAYLOAD_INVALID",
    "open_reauthorization_denied": "NOTIFICATION_OPEN_REAUTHORIZATION_DENIED",
    "cancellation_denied": "NOTIFICATION_CANCELLATION_DENIED",
    "dependency_unavailable": "NOTIFICATION_DEPENDENCY_UNAVAILABLE",
    "sensitivity_invalid": "NOTIFICATION_SENSITIVITY_INVALID",
}

EXPECTED_PUBLIC_ERRORS = {
    "concealed": "NOTIFICATION_NOT_FOUND",
    "not_available": "NOTIFICATION_NOT_AVAILABLE",
    "invalid": "NOTIFICATION_REQUEST_INVALID",
    "dependency_unavailable": "NOTIFICATION_DELIVERY_UNAVAILABLE",
}

EXPECTED_AUDIT_ACTIONS = {
    "NOTIFICATION_DISPATCH_GRANTED",
    "NOTIFICATION_DISPATCH_DENIED",
    "NOTIFICATION_DELIVERED",
    "NOTIFICATION_DELIVERY_FAILED",
    "NOTIFICATION_RETRY_SCHEDULED",
    "NOTIFICATION_DEAD_LETTERED",
    "NOTIFICATION_OPEN_GRANTED",
    "NOTIFICATION_OPEN_DENIED",
    "NOTIFICATION_CANCELLED",
    "NOTIFICATION_EXPIRED",
    "DEVICE_ENDPOINT_REVOKED",
}

EXPECTED_DISPATCH_CHECKS = {
    "exact_active_policy_version_and_named_approvals",
    "trusted_notification_and_source_service_identity",
    "approved_source_delegation",
    "active_verified_recipient_identity",
    "tenant_and_school_scope",
    "current_object_relationship",
    "exact_current_permission",
    "approved_purpose",
    "authoritative_consent_decision",
    "content_class_channel_and_template_allowlist",
    "source_notification_eligibility_and_state",
    "source_and_notification_expiry",
    "current_endpoint_owner_verification_and_preference",
    "deduplication_and_cancellation_state",
}

EXPECTED_OPEN_CHECKS = {
    "authenticated_current_recipient",
    "notification_not_expired_or_cancelled",
    "fresh_tenant_school_object_relationship",
    "fresh_permission_purpose_and_consent",
    "fresh_source_state_and_retention",
    "resource_service_authorization",
}

EXPECTED_ENDPOINT_FORBIDDEN_DESTINATIONS = {
    "audit",
    "log",
    "trace",
    "queue",
    "dead_letter",
    "notification_content",
    "response",
    "support_export",
}

EXPECTED_AUDIT_REQUIRED_FIELDS = {
    "opaque_actor_or_service_ref",
    "opaque_recipient_ref",
    "tenant_ref",
    "school_ref",
    "opaque_notification_ref",
    "opaque_resource_ref",
    "channel",
    "content_class",
    "template_version",
    "policy_version",
    "purpose_code",
    "outcome",
    "stable_reason_code",
    "request_id",
    "correlation_id",
    "occurred_at",
}

EXPECTED_AUDIT_OPTIONAL_FIELDS = {
    "attempt_count",
    "stable_provider_result_category",
    "expires_at",
    "cancellation_trigger",
}

EXPECTED_AUDIT_FORBIDDEN_FIELDS = {
    "recipient_name",
    "email_address",
    "phone_number",
    "device_token",
    "endpoint_ciphertext",
    "endpoint_fingerprint",
    "message_text",
    "template_parameters",
    "signed_url",
    "bucket_name",
    "object_key",
    "provider_locator",
    "media_binary",
    "image_base64",
    "face_embedding",
    "raw_ansvis_payload",
    "access_token",
    "credential",
    "personal_profile",
    "free_form_note",
}

EXPECTED_SUPERSESSION_TRIGGERS = {
    "role_or_relationship_change",
    "channel_or_content_change",
    "permission_or_purpose_change",
    "consent_or_authorization_change",
    "endpoint_or_provider_boundary_change",
    "expiry_retry_dead_letter_or_cancellation_change",
    "audit_or_error_change",
    "customer_legal_or_security_finding",
    "runtime_activation_change",
}

EXPECTED_SUPERSESSION_EVIDENCE = {
    "compatibility_matrix",
    "privacy_legal_approval",
    "security_ops_approval",
    "business_owner_approval",
    "rollback_and_supersession_record",
}

CONTEXT_FIELDS = {
    "operation",
    "notification_service_identity_trusted",
    "notification_service_permission_code",
    "source_service_identity_trusted",
    "source_service_permission_code",
    "source_delegation_status",
    "provider_adapter_identity_trusted",
    "provider_adapter_permission_code",
    "recipient_authenticated",
    "recipient_identity_status",
    "recipient_role",
    "recipient_relationship",
    "tenant_scope_match",
    "school_scope_match",
    "resource_exists",
    "resource_scope_match",
    "permission_code",
    "permission_status",
    "purpose_code",
    "purpose_status",
    "consent_status",
    "consent_decision_authoritative",
    "policy_version_status",
    "runtime_approval_status",
    "notification_sensitivity",
    "channel",
    "channel_preference_status",
    "content_class",
    "template_code",
    "template_version",
    "content_fields",
    "source_state",
    "source_notification_eligible",
    "source_retention_status",
    "notification_state",
    "notification_expiry_status",
    "source_expiry_status",
    "endpoint_status",
    "endpoint_owner_match",
    "endpoint_verified",
    "endpoint_protection_status",
    "deduplication_state",
    "authorization_dependencies_available",
    "provider_dependency_available",
    "retry_limit_status",
    "retry_attempt_status",
    "retry_window_status",
    "retry_payload_minimized",
    "dead_letter_fields",
    "dead_letter_expiry_status",
    "open_resource_authorization_status",
    "cancellation_trigger",
    "cancellation_owner_authorized",
}

BOOLEAN_CONTEXT_FIELDS = {
    "notification_service_identity_trusted",
    "source_service_identity_trusted",
    "provider_adapter_identity_trusted",
    "recipient_authenticated",
    "tenant_scope_match",
    "school_scope_match",
    "resource_exists",
    "resource_scope_match",
    "consent_decision_authoritative",
    "source_notification_eligible",
    "endpoint_owner_match",
    "endpoint_verified",
    "authorization_dependencies_available",
    "provider_dependency_available",
    "retry_payload_minimized",
    "cancellation_owner_authorized",
}

LIST_CONTEXT_FIELDS = {"content_fields", "dead_letter_fields"}
INTEGER_CONTEXT_FIELDS = {"template_version"}


class NotificationPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ChannelPolicy:
    required_fields: frozenset[str]
    allowed_fields: frozenset[str]


@dataclass(frozen=True)
class ContentPolicy:
    template_code: str
    template_version: int
    permission_code: str
    purpose_code: str
    allowed_channels: frozenset[str]
    allowed_source_states: frozenset[str]
    candidate_recipient_roles: frozenset[str]


@dataclass(frozen=True)
class RecipientPolicy:
    relationships: frozenset[str]
    content_classes: frozenset[str]
    channels: frozenset[str]


@dataclass(frozen=True)
class NotificationPolicy:
    channels: dict[str, ChannelPolicy]
    content_classes: dict[str, ContentPolicy]
    recipient_roles: dict[str, RecipientPolicy]
    prohibited_fields: frozenset[str]
    dead_letter_fields: frozenset[str]
    cancellation_triggers: frozenset[str]
    reason_codes: dict[str, str]
    public_errors: dict[str, str]


@dataclass(frozen=True)
class Decision:
    decision: str
    reason_code: str
    public_error: str


def _fail(code: str, detail: str) -> NoReturn:
    raise NotificationPolicyError(f"{code}: {detail}")


def _expect_keys(
    value: object,
    expected: set[str],
    *,
    code: str,
    location: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(code, f"{location} must be an object")
    typed = cast(dict[str, object], value)
    actual = set(typed)
    if actual != expected:
        _fail(code, f"{location} keys mismatch")
    return typed


def _text(value: object, *, code: str, location: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(code, f"{location} must be non-empty text")
    return value


def _boolean(value: object, *, code: str, location: str) -> bool:
    if not isinstance(value, bool):
        _fail(code, f"{location} must be boolean")
    return value


def _text_set(value: object, *, code: str, location: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        _fail(code, f"{location} must be a non-empty-text array")
    result = set(cast(list[str], value))
    if len(result) != len(value):
        _fail(code, f"{location} contains duplicates")
    return result


def _validate_exact_object(
    value: object,
    expected: Mapping[str, object],
    *,
    location: str,
) -> None:
    document = _expect_keys(
        value,
        set(expected),
        code=NOTIFICATION_POLICY_INVALID,
        location=location,
    )
    for key, expected_value in expected.items():
        actual = document[key]
        if isinstance(expected_value, set):
            if (
                _text_set(
                    actual,
                    code=NOTIFICATION_POLICY_INVALID,
                    location=f"{location}.{key}",
                )
                != expected_value
            ):
                _fail(
                    NOTIFICATION_POLICY_INVALID,
                    f"{location}.{key} differs from v1",
                )
        elif actual != expected_value:
            _fail(
                NOTIFICATION_POLICY_INVALID,
                f"{location}.{key} differs from v1",
            )


def validate_policy(document: dict[str, object]) -> NotificationPolicy:
    expected_top = {
        "policy_id",
        "version",
        "status",
        "owner",
        "data_classifications",
        "runtime_activation",
        "operations",
        "channels",
        "globally_prohibited_fields",
        "content_classes",
        "recipient_role_matrix",
        "service_actor_matrix",
        "authorization",
        "endpoint_protection",
        "expiry_retry_and_dead_letter",
        "audit",
        "stable_reason_codes",
        "public_errors",
        "supersession",
    }
    _expect_keys(
        document,
        expected_top,
        code=NOTIFICATION_POLICY_INVALID,
        location="policy",
    )
    if (
        document["policy_id"] != "notification_privacy_policy_v1"
        or document["version"] != 1
        or document["status"] != "approved_for_implementation"
        or document["owner"] != "notification_privacy_owner"
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "identity metadata differs from v1")

    _validate_exact_object(
        document["data_classifications"],
        {
            "recipient_identity_relationship_and_device_endpoint": "Critical",
            "notification_content_resource_and_delivery_state": "High_or_Critical",
            "audit_and_operational_metadata": "High_minimized",
        },
        location="data_classifications",
    )
    runtime = _expect_keys(
        document["runtime_activation"],
        {
            "status",
            "required_approvals",
            "missing_or_inactive_policy_behavior",
            "synthetic_allow_cases_assume_future_named_approvals",
        },
        code=NOTIFICATION_POLICY_INVALID,
        location="runtime_activation",
    )
    if (
        runtime["status"] != "blocked_pending_named_approvals"
        or runtime["missing_or_inactive_policy_behavior"] != "deny"
        or runtime["synthetic_allow_cases_assume_future_named_approvals"] is not True
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "runtime activation must remain blocked")
    _validate_exact_object(
        runtime["required_approvals"],
        {
            "privacy_legal": "pending",
            "security_ops": "pending",
            "business_owner": "pending",
        },
        location="runtime_activation.required_approvals",
    )
    if (
        _text_set(
            document["operations"],
            code=NOTIFICATION_POLICY_INVALID,
            location="operations",
        )
        != EXPECTED_OPERATIONS
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "operations differ from v1")

    channels_doc = _expect_keys(
        document["channels"],
        set(EXPECTED_CHANNELS),
        code=NOTIFICATION_POLICY_INVALID,
        location="channels",
    )
    channels: dict[str, ChannelPolicy] = {}
    for name, expected in EXPECTED_CHANNELS.items():
        _validate_exact_object(
            channels_doc[name],
            expected,
            location=f"channels.{name}",
        )
        channels[name] = ChannelPolicy(
            required_fields=frozenset(cast(set[str], expected["required_fields"])),
            allowed_fields=frozenset(cast(set[str], expected["allowed_fields"])),
        )

    prohibited = _text_set(
        document["globally_prohibited_fields"],
        code=NOTIFICATION_POLICY_INVALID,
        location="globally_prohibited_fields",
    )
    if prohibited != EXPECTED_PROHIBITED_FIELDS:
        _fail(NOTIFICATION_POLICY_INVALID, "prohibited fields differ from v1")
    for channel in channels.values():
        if channel.allowed_fields & prohibited:
            _fail(
                NOTIFICATION_POLICY_INVALID,
                "allowed channel fields overlap prohibited fields",
            )

    content_doc = _expect_keys(
        document["content_classes"],
        set(EXPECTED_CONTENT_CLASSES),
        code=NOTIFICATION_POLICY_INVALID,
        location="content_classes",
    )
    contents: dict[str, ContentPolicy] = {}
    for name, content_expected in EXPECTED_CONTENT_CLASSES.items():
        _validate_exact_object(
            content_doc[name],
            content_expected,
            location=f"content_classes.{name}",
        )
        contents[name] = ContentPolicy(
            template_code=cast(str, content_expected["template_code"]),
            template_version=cast(int, content_expected["template_version"]),
            permission_code=cast(str, content_expected["permission_code"]),
            purpose_code=cast(str, content_expected["purpose_code"]),
            allowed_channels=frozenset(cast(set[str], content_expected["allowed_channels"])),
            allowed_source_states=frozenset(
                cast(set[str], content_expected["allowed_source_states"])
            ),
            candidate_recipient_roles=frozenset(
                cast(set[str], content_expected["candidate_recipient_roles"])
            ),
        )

    roles_doc = _expect_keys(
        document["recipient_role_matrix"],
        set(EXPECTED_RECIPIENT_ROLES),
        code=NOTIFICATION_POLICY_INVALID,
        location="recipient_role_matrix",
    )
    roles: dict[str, RecipientPolicy] = {}
    for name, role_expected in EXPECTED_RECIPIENT_ROLES.items():
        _validate_exact_object(
            roles_doc[name],
            role_expected,
            location=f"recipient_role_matrix.{name}",
        )
        roles[name] = RecipientPolicy(
            relationships=frozenset(role_expected["relationships"]),
            content_classes=frozenset(role_expected["content_classes"]),
            channels=frozenset(role_expected["channels"]),
        )

    service_doc = _expect_keys(
        document["service_actor_matrix"],
        {"notification_service", "source_business_service", "provider_adapter"},
        code=NOTIFICATION_POLICY_INVALID,
        location="service_actor_matrix",
    )
    _validate_exact_object(
        service_doc["notification_service"],
        {
            "trusted_identity_required": True,
            "permission_code": "service.notification.dispatch",
            "allowed_operations": EXPECTED_OPERATIONS,
        },
        location="service_actor_matrix.notification_service",
    )
    _validate_exact_object(
        service_doc["source_business_service"],
        {
            "trusted_identity_required": True,
            "permission_code": "service.notification.request",
            "delegation_required": True,
        },
        location="service_actor_matrix.source_business_service",
    )
    _validate_exact_object(
        service_doc["provider_adapter"],
        {
            "trusted_identity_required": True,
            "permission_code": "service.notification.provider_deliver",
            "required_channels": {"push", "email"},
        },
        location="service_actor_matrix.provider_adapter",
    )

    expiry = _expect_keys(
        document["expiry_retry_and_dead_letter"],
        {
            "notification_expires_at_required",
            "source_expires_at_required",
            "notification_must_not_outlive_source_or_purpose",
            "retry_profile_requires_named_approved_limits",
            "missing_retry_limit_behavior",
            "retry_must_reauthorize_before_each_attempt",
            "retry_must_finish_before_notification_and_source_expiry",
            "dead_letter_payload_allowed_fields",
            "dead_letter_never_extends_retention_or_authority",
            "deduplication_behavior",
            "cancellation_triggers",
        },
        code=NOTIFICATION_POLICY_INVALID,
        location="expiry_retry_and_dead_letter",
    )
    for boolean_name in {
        "notification_expires_at_required",
        "source_expires_at_required",
        "notification_must_not_outlive_source_or_purpose",
        "retry_profile_requires_named_approved_limits",
        "retry_must_reauthorize_before_each_attempt",
        "retry_must_finish_before_notification_and_source_expiry",
        "dead_letter_never_extends_retention_or_authority",
    }:
        if expiry[boolean_name] is not True:
            _fail(
                NOTIFICATION_POLICY_INVALID,
                f"expiry_retry_and_dead_letter.{boolean_name} must stay true",
            )
    if (
        expiry["missing_retry_limit_behavior"] != "deny"
        or expiry["deduplication_behavior"]
        != "suppress_duplicate_without_duplicate_content_or_audit_payload"
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "retry/dedup behavior differs from v1")
    dead_letter_fields = _text_set(
        expiry["dead_letter_payload_allowed_fields"],
        code=NOTIFICATION_POLICY_INVALID,
        location="expiry_retry_and_dead_letter.dead_letter_payload_allowed_fields",
    )
    cancellation_triggers = _text_set(
        expiry["cancellation_triggers"],
        code=NOTIFICATION_POLICY_INVALID,
        location="expiry_retry_and_dead_letter.cancellation_triggers",
    )
    if dead_letter_fields != EXPECTED_DEAD_LETTER_FIELDS:
        _fail(NOTIFICATION_POLICY_INVALID, "dead-letter fields differ from v1")
    if cancellation_triggers != EXPECTED_CANCELLATION_TRIGGERS:
        _fail(NOTIFICATION_POLICY_INVALID, "cancellation triggers differ from v1")
    if dead_letter_fields & prohibited:
        _fail(
            NOTIFICATION_POLICY_INVALID,
            "dead-letter fields overlap prohibited fields",
        )

    audit = _expect_keys(
        document["audit"],
        {
            "actions",
            "required_fields",
            "optional_minimized_fields",
            "forbidden_fields",
            "allowed_and_denied_are_append_only",
        },
        code=NOTIFICATION_POLICY_INVALID,
        location="audit",
    )
    if (
        _text_set(
            audit["actions"],
            code=NOTIFICATION_POLICY_INVALID,
            location="audit.actions",
        )
        != EXPECTED_AUDIT_ACTIONS
        or audit["allowed_and_denied_are_append_only"] is not True
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "audit actions/immutability differ from v1")
    audit_required = _text_set(
        audit["required_fields"],
        code=NOTIFICATION_POLICY_INVALID,
        location="audit.required_fields",
    )
    audit_optional = _text_set(
        audit["optional_minimized_fields"],
        code=NOTIFICATION_POLICY_INVALID,
        location="audit.optional_minimized_fields",
    )
    audit_forbidden = _text_set(
        audit["forbidden_fields"],
        code=NOTIFICATION_POLICY_INVALID,
        location="audit.forbidden_fields",
    )
    if (
        audit_required != EXPECTED_AUDIT_REQUIRED_FIELDS
        or audit_optional != EXPECTED_AUDIT_OPTIONAL_FIELDS
        or audit_forbidden != EXPECTED_AUDIT_FORBIDDEN_FIELDS
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "audit fields differ from v1")
    if audit_required & audit_forbidden or audit_optional & audit_forbidden:
        _fail(NOTIFICATION_POLICY_INVALID, "audit fields overlap forbidden fields")

    reason_doc = _expect_keys(
        document["stable_reason_codes"],
        set(EXPECTED_REASON_CODES),
        code=NOTIFICATION_POLICY_INVALID,
        location="stable_reason_codes",
    )
    if reason_doc != EXPECTED_REASON_CODES:
        _fail(NOTIFICATION_POLICY_INVALID, "reason codes differ from v1")
    public_doc = _expect_keys(
        document["public_errors"],
        set(EXPECTED_PUBLIC_ERRORS),
        code=NOTIFICATION_POLICY_INVALID,
        location="public_errors",
    )
    if public_doc != EXPECTED_PUBLIC_ERRORS:
        _fail(NOTIFICATION_POLICY_INVALID, "public errors differ from v1")

    authorization = _expect_keys(
        document["authorization"],
        {
            "dispatch_checks",
            "open_checks",
            "notification_payload_is_never_authority",
            "wrong_recipient_scope_and_missing_resource_share_public_error",
        },
        code=NOTIFICATION_POLICY_INVALID,
        location="authorization",
    )
    if (
        authorization["notification_payload_is_never_authority"] is not True
        or authorization["wrong_recipient_scope_and_missing_resource_share_public_error"]
        is not True
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "authorization fail-closed flags missing")
    if (
        _text_set(
            authorization["dispatch_checks"],
            code=NOTIFICATION_POLICY_INVALID,
            location="authorization.dispatch_checks",
        )
        != EXPECTED_DISPATCH_CHECKS
        or _text_set(
            authorization["open_checks"],
            code=NOTIFICATION_POLICY_INVALID,
            location="authorization.open_checks",
        )
        != EXPECTED_OPEN_CHECKS
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "authorization checks differ from v1")

    endpoint = _expect_keys(
        document["endpoint_protection"],
        {
            "device_token_storage",
            "device_token_exact_lookup",
            "email_endpoint_storage",
            "plaintext_boundary",
            "required_status",
            "revoked_inactive_reassigned_or_ambiguous_behavior",
            "invalid_provider_endpoint_behavior",
            "forbidden_destinations",
        },
        code=NOTIFICATION_POLICY_INVALID,
        location="endpoint_protection",
    )
    if (
        endpoint["device_token_storage"] != "ENCV1_ciphertext"
        or endpoint["device_token_exact_lookup"] != "LOOKUP-V1/device-token-v1"
        or endpoint["email_endpoint_storage"] != "ENCV1_ciphertext"
        or endpoint["plaintext_boundary"] != "provider_dispatch_only"
        or endpoint["required_status"] != "active_verified_owned"
        or endpoint["revoked_inactive_reassigned_or_ambiguous_behavior"]
        != "deny_and_cancel_pending"
        or endpoint["invalid_provider_endpoint_behavior"] != "revoke_without_logging_endpoint_value"
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "endpoint protection differs from v1")
    endpoint_destinations = _text_set(
        endpoint["forbidden_destinations"],
        code=NOTIFICATION_POLICY_INVALID,
        location="endpoint_protection.forbidden_destinations",
    )
    if endpoint_destinations != EXPECTED_ENDPOINT_FORBIDDEN_DESTINATIONS:
        _fail(
            NOTIFICATION_POLICY_INVALID,
            "endpoint forbidden destinations differ from v1",
        )

    supersession = _expect_keys(
        document["supersession"],
        {
            "published_versions_are_immutable",
            "requires_new_version_for",
            "required_evidence",
        },
        code=NOTIFICATION_POLICY_INVALID,
        location="supersession",
    )
    if supersession["published_versions_are_immutable"] is not True:
        _fail(NOTIFICATION_POLICY_INVALID, "published v1 must be immutable")
    if (
        _text_set(
            supersession["requires_new_version_for"],
            code=NOTIFICATION_POLICY_INVALID,
            location="supersession.requires_new_version_for",
        )
        != EXPECTED_SUPERSESSION_TRIGGERS
        or _text_set(
            supersession["required_evidence"],
            code=NOTIFICATION_POLICY_INVALID,
            location="supersession.required_evidence",
        )
        != EXPECTED_SUPERSESSION_EVIDENCE
    ):
        _fail(NOTIFICATION_POLICY_INVALID, "supersession contract differs from v1")

    return NotificationPolicy(
        channels=channels,
        content_classes=contents,
        recipient_roles=roles,
        prohibited_fields=frozenset(prohibited),
        dead_letter_fields=frozenset(dead_letter_fields),
        cancellation_triggers=frozenset(cancellation_triggers),
        reason_codes=cast(dict[str, str], reason_doc),
        public_errors=cast(dict[str, str], public_doc),
    )


def _validate_context(context: dict[str, object]) -> None:
    _expect_keys(
        context,
        CONTEXT_FIELDS,
        code=NOTIFICATION_FIXTURE_INVALID,
        location="context",
    )
    for name, value in context.items():
        if name in BOOLEAN_CONTEXT_FIELDS:
            _boolean(
                value,
                code=NOTIFICATION_FIXTURE_INVALID,
                location=f"context.{name}",
            )
        elif name in LIST_CONTEXT_FIELDS:
            _text_set(
                value,
                code=NOTIFICATION_FIXTURE_INVALID,
                location=f"context.{name}",
            )
        elif name in INTEGER_CONTEXT_FIELDS:
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                _fail(
                    NOTIFICATION_FIXTURE_INVALID,
                    f"context.{name} must be a positive integer",
                )
        else:
            _text(
                value,
                code=NOTIFICATION_FIXTURE_INVALID,
                location=f"context.{name}",
            )


def _deny(
    policy: NotificationPolicy,
    reason: str,
    public_error: str,
) -> Decision:
    return Decision(
        decision="deny",
        reason_code=policy.reason_codes[reason],
        public_error=policy.public_errors[public_error],
    )


def _allow(policy: NotificationPolicy, reason: str) -> Decision:
    return Decision(
        decision="allow",
        reason_code=policy.reason_codes[reason],
        public_error="",
    )


def evaluate_notification(
    context: dict[str, object],
    policy: NotificationPolicy,
) -> Decision:
    _validate_context(context)
    operation = cast(str, context["operation"])

    if operation not in EXPECTED_OPERATIONS:
        return _deny(policy, "content_denied", "invalid")
    if (
        context["policy_version_status"] != "active"
        or context["runtime_approval_status"] != "approved"
    ):
        return _deny(policy, "policy_inactive", "dependency_unavailable")
    if (
        context["notification_service_identity_trusted"] is not True
        or context["notification_service_permission_code"] != "service.notification.dispatch"
    ):
        return _deny(policy, "service_identity_denied", "concealed")
    if operation in {"dispatch", "retry", "dead_letter"}:
        if (
            context["source_service_identity_trusted"] is not True
            or context["source_service_permission_code"] != "service.notification.request"
        ):
            return _deny(policy, "source_service_denied", "concealed")
        if context["source_delegation_status"] != "approved":
            return _deny(policy, "delegation_required", "concealed")
    if context["recipient_authenticated"] is not True:
        return _deny(policy, "recipient_unauthenticated", "concealed")
    if context["recipient_identity_status"] != "active_verified":
        return _deny(policy, "recipient_inactive", "concealed")
    if context["notification_sensitivity"] not in {"High", "Critical"}:
        return _deny(policy, "sensitivity_invalid", "invalid")
    if context["authorization_dependencies_available"] is not True:
        return _deny(policy, "dependency_unavailable", "dependency_unavailable")

    role_name = cast(str, context["recipient_role"])
    content_name = cast(str, context["content_class"])
    channel_name = cast(str, context["channel"])
    role = policy.recipient_roles.get(role_name)
    content = policy.content_classes.get(content_name)
    channel = policy.channels.get(channel_name)
    if content is None or channel is None:
        return _deny(policy, "content_denied", "invalid")
    if role is None:
        return _deny(policy, "recipient_scope_denied", "concealed")
    if content_name not in role.content_classes:
        return _deny(policy, "content_denied", "concealed")
    if role_name not in content.candidate_recipient_roles:
        return _deny(policy, "content_denied", "concealed")
    if (
        context["template_code"] != content.template_code
        or context["template_version"] != content.template_version
    ):
        return _deny(policy, "content_denied", "invalid")
    if cast(str, context["recipient_relationship"]) not in role.relationships:
        return _deny(policy, "recipient_scope_denied", "concealed")
    if not all(
        context[name] is True
        for name in (
            "tenant_scope_match",
            "school_scope_match",
            "resource_exists",
            "resource_scope_match",
        )
    ):
        return _deny(policy, "recipient_scope_denied", "concealed")
    if (
        context["permission_code"] != content.permission_code
        or context["permission_status"] != "active"
    ):
        return _deny(policy, "permission_denied", "concealed")
    if context["purpose_code"] != content.purpose_code or context["purpose_status"] != "approved":
        return _deny(policy, "purpose_denied", "concealed")
    if context["consent_decision_authoritative"] is not True or context["consent_status"] not in {
        "allowed",
        "not_required",
    }:
        return _deny(policy, "consent_denied", "concealed")

    if operation == "cancel":
        if (
            context["cancellation_owner_authorized"] is not True
            or cast(str, context["cancellation_trigger"]) not in policy.cancellation_triggers
        ):
            public = (
                "concealed" if context["cancellation_owner_authorized"] is not True else "invalid"
            )
            return _deny(policy, "cancellation_denied", public)
        return _allow(policy, "cancellation_allowed")

    if context["notification_state"] == "cancelled":
        return _deny(policy, "cancelled", "not_available")
    if context["notification_state"] != "eligible":
        return _deny(policy, "source_not_eligible", "not_available")
    if (
        context["notification_expiry_status"] != "current"
        or context["source_expiry_status"] != "current"
    ):
        return _deny(policy, "expired", "not_available")
    if (
        context["source_notification_eligible"] is not True
        or context["source_retention_status"] != "current"
        or cast(str, context["source_state"]) not in content.allowed_source_states
    ):
        return _deny(policy, "source_not_eligible", "not_available")

    if operation == "open":
        if context["open_resource_authorization_status"] != "granted":
            return _deny(policy, "open_reauthorization_denied", "concealed")
        return _allow(policy, "open_allowed")

    if channel_name not in role.channels or channel_name not in content.allowed_channels:
        return _deny(policy, "channel_denied", "concealed")
    if context["channel_preference_status"] != "enabled":
        return _deny(policy, "channel_denied", "not_available")

    if operation in {"dispatch", "retry"}:
        content_fields = _text_set(
            context["content_fields"],
            code=NOTIFICATION_FIXTURE_INVALID,
            location="context.content_fields",
        )
        if (
            content_fields & policy.prohibited_fields
            or not channel.required_fields <= content_fields
            or not content_fields <= channel.allowed_fields
        ):
            return _deny(policy, "content_denied", "invalid")
        if channel_name in {"push", "email"}:
            if (
                context["provider_adapter_identity_trusted"] is not True
                or context["provider_adapter_permission_code"]
                != "service.notification.provider_deliver"
            ):
                return _deny(policy, "provider_adapter_denied", "concealed")
            if (
                context["endpoint_status"] != "active"
                or context["endpoint_owner_match"] is not True
                or context["endpoint_verified"] is not True
                or context["endpoint_protection_status"]
                not in {"encrypted_tokenized", "encrypted_endpoint"}
            ):
                public = (
                    "concealed" if context["endpoint_owner_match"] is not True else "not_available"
                )
                return _deny(policy, "endpoint_denied", public)
            if context["provider_dependency_available"] is not True:
                return _deny(
                    policy,
                    "dependency_unavailable",
                    "dependency_unavailable",
                )
        elif (
            context["endpoint_status"] != "not_required"
            or context["endpoint_protection_status"] != "not_required"
        ):
            return _deny(policy, "endpoint_denied", "invalid")

    if operation == "dispatch":
        if context["deduplication_state"] != "new":
            return _deny(policy, "duplicate_suppressed", "not_available")
        return _allow(policy, "dispatch_allowed")
    if operation == "retry":
        if (
            context["retry_limit_status"] != "named_approved"
            or context["retry_attempt_status"] != "within_limit"
            or context["retry_payload_minimized"] is not True
        ):
            return _deny(policy, "retry_denied", "invalid")
        if context["retry_window_status"] != "within_expiry":
            return _deny(policy, "retry_denied", "not_available")
        return _allow(policy, "retry_allowed")
    if operation == "dead_letter":
        fields = _text_set(
            context["dead_letter_fields"],
            code=NOTIFICATION_FIXTURE_INVALID,
            location="context.dead_letter_fields",
        )
        if fields != policy.dead_letter_fields:
            return _deny(policy, "dead_letter_payload_invalid", "invalid")
        if context["dead_letter_expiry_status"] != "within_source_expiry":
            return _deny(
                policy,
                "dead_letter_payload_invalid",
                "not_available",
            )
        return _allow(policy, "dead_letter_allowed")
    return _deny(policy, "content_denied", "invalid")


def validate_fixture(
    document: dict[str, object],
    policy: NotificationPolicy,
) -> int:
    fixture = _expect_keys(
        document,
        {
            "_fixture",
            "fixture_id",
            "synthetic_only",
            "contains_real_personal_data",
            "contains_real_endpoint_or_token",
            "default_context",
            "cases",
        },
        code=NOTIFICATION_FIXTURE_INVALID,
        location="fixture",
    )
    if (
        fixture["_fixture"] != "SYNTHETIC_TEST_DATA_ONLY"
        or fixture["fixture_id"] != "test_notification_privacy_policy_v1_cases"
        or fixture["synthetic_only"] is not True
        or fixture["contains_real_personal_data"] is not False
        or fixture["contains_real_endpoint_or_token"] is not False
    ):
        _fail(NOTIFICATION_FIXTURE_INVALID, "fixture safety metadata is invalid")
    default_context = _expect_keys(
        fixture["default_context"],
        CONTEXT_FIELDS,
        code=NOTIFICATION_FIXTURE_INVALID,
        location="fixture.default_context",
    )
    _validate_context(default_context)
    raw_cases = fixture["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        _fail(NOTIFICATION_FIXTURE_INVALID, "cases must be a non-empty array")
    cases = cast(list[object], raw_cases)

    seen: set[str] = set()
    for index, raw_case in enumerate(cases):
        case = _expect_keys(
            raw_case,
            {
                "case_code",
                "overrides",
                "expected_decision",
                "expected_reason_code",
                "expected_public_error",
            },
            code=NOTIFICATION_FIXTURE_INVALID,
            location=f"cases[{index}]",
        )
        case_code = _text(
            case["case_code"],
            code=NOTIFICATION_FIXTURE_INVALID,
            location=f"cases[{index}].case_code",
        )
        if case_code in seen:
            _fail(NOTIFICATION_FIXTURE_INVALID, f"duplicate case {case_code}")
        seen.add(case_code)
        overrides = case["overrides"]
        if not isinstance(overrides, dict) or not all(isinstance(key, str) for key in overrides):
            _fail(
                NOTIFICATION_FIXTURE_INVALID,
                f"cases[{index}].overrides must be an object",
            )
        typed_overrides = cast(dict[str, object], overrides)
        if not set(typed_overrides) <= CONTEXT_FIELDS:
            _fail(
                NOTIFICATION_FIXTURE_INVALID,
                f"cases[{index}].overrides contains unknown context fields",
            )
        context = dict(default_context)
        context.update(typed_overrides)
        decision = evaluate_notification(context, policy)
        expected_decision = _text(
            case["expected_decision"],
            code=NOTIFICATION_FIXTURE_INVALID,
            location=f"cases[{index}].expected_decision",
        )
        expected_reason = _text(
            case["expected_reason_code"],
            code=NOTIFICATION_FIXTURE_INVALID,
            location=f"cases[{index}].expected_reason_code",
        )
        expected_public = case["expected_public_error"]
        if not isinstance(expected_public, str):
            _fail(
                NOTIFICATION_FIXTURE_INVALID,
                f"cases[{index}].expected_public_error must be text",
            )
        if (
            decision.decision != expected_decision
            or decision.reason_code != expected_reason
            or decision.public_error != expected_public
        ):
            _fail(
                NOTIFICATION_FIXTURE_INVALID,
                f"{case_code} expected "
                f"{expected_decision}/{expected_reason}/{expected_public!r}, got "
                f"{decision.decision}/{decision.reason_code}/"
                f"{decision.public_error!r}",
            )
    return len(cases)


def _load_document(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(NOTIFICATION_POLICY_INVALID, f"cannot load {path}: {exc}")
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(NOTIFICATION_POLICY_INVALID, f"{path} must contain an object")
    return cast(dict[str, object], value)


def main() -> int:
    try:
        policy = validate_policy(_load_document(POLICY_PATH))
        checked = validate_fixture(_load_document(FIXTURE_PATH), policy)
    except NotificationPolicyError as exc:
        print(f"notification_privacy_policy=FAIL ({exc})")
        return 1
    print("notification_privacy_policy=PASS")
    print("policy_version=notification_privacy_policy_v1")
    print("runtime_activation=BLOCKED_PENDING_NAMED_APPROVALS")
    print(f"synthetic_cases_checked={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
