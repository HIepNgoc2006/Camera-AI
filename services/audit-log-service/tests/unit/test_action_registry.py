from __future__ import annotations

from audit_log_service.domain.models import AuditResult
from audit_log_service.domain.policies import ACTION_POLICIES, APPROVED_ACTIONS


def test_registry_contains_the_approved_cross_domain_audit_taxonomy() -> None:
    required = {
        "AUTH_LOGIN_SUCCEEDED",
        "CONSENT_REQUESTED",
        "CONSENT_RESTRICTED",
        "CONSENT_WITHDRAWN",
        "ANSVIS_SOURCE_AUTH_DENIED",
        "ATTENDANCE_CORRECTION_DECIDED",
        "TIMEKEEPING_EXPORTED",
        "VIOLATION_REVIEW_DECIDED",
        "EVIDENCE_VIEW_DENIED",
        "REPORT_EXPORT_DOWNLOADED",
        "MODEL_DEPLOYMENT_CHANGED",
        "KEY_COMPROMISE_DECLARED",
        "RETENTION_DELETE_FAILED",
        "BACKUP_RESTORE_FAILED",
        "AUDIT_INTEGRITY_FAILED",
    }

    assert required <= APPROVED_ACTIONS
    assert len(APPROVED_ACTIONS) >= 82
    assert len(APPROVED_ACTIONS) == len(ACTION_POLICIES)


def test_consent_change_actions_keep_business_result_semantics() -> None:
    assert ACTION_POLICIES["CONSENT_DENIED"].results == frozenset({AuditResult.DENIED})
    for action in (
        "CONSENT_REQUESTED",
        "CONSENT_GRANTED",
        "CONSENT_WITHDRAWN",
        "CONSENT_EXPIRED",
        "CONSENT_RESTRICTED",
    ):
        assert ACTION_POLICIES[action].results == frozenset({AuditResult.SUCCESS})


def test_event_consent_denial_policy_binds_the_ingestion_publisher_and_versions() -> None:
    policy = ACTION_POLICIES["EVENT_CONSENT_DENIED"]

    assert policy.publishers == frozenset({"event-ingestion-service"})
    assert policy.resource_types == frozenset({"event", "ingestion_receipt"})
    assert policy.results == frozenset({AuditResult.DENIED})
    assert policy.purpose_required is False
    assert policy.school_scope_required is True
    assert policy.resource_identity_required is True
    assert policy.reference_types == frozenset({"event_id", "receipt_id", "outbox_id"})
    assert policy.policy_types == frozenset({"consent_policy"})
    assert policy.changed_fields == frozenset()


def test_camera_registry_policy_accepts_minimized_zone_and_camera_changes() -> None:
    policy = ACTION_POLICIES["CAMERA_MAPPING_CHANGED"]

    assert policy.publishers == frozenset({"camera-registry-service"})
    assert policy.resource_types == frozenset({"camera", "camera_zone"})
    assert policy.purpose_required is True
    assert {"metadata", "purpose", "schedule", "status", "task", "zone"} <= (policy.changed_fields)


def test_notification_policy_accepts_only_minimized_service_actions() -> None:
    delivery_actions = {
        "NOTIFICATION_DISPATCH_GRANTED",
        "NOTIFICATION_DISPATCH_DENIED",
        "NOTIFICATION_DELIVERED",
        "NOTIFICATION_RETRY_SCHEDULED",
        "NOTIFICATION_DEAD_LETTERED",
        "NOTIFICATION_OPEN_GRANTED",
        "NOTIFICATION_OPEN_DENIED",
        "NOTIFICATION_CANCELLED",
    }
    assert delivery_actions <= APPROVED_ACTIONS
    for action in delivery_actions:
        policy = ACTION_POLICIES[action]
        assert policy.publishers == frozenset({"notification-service"})
        assert policy.purpose_required
        assert policy.reference_types == frozenset(
            {"delivery_id", "notification_id", "recipient_id", "resource_id"}
        )
        assert policy.policy_types == frozenset({"notification_policy", "rbac_policy"})

    for action in ("DEVICE_ENDPOINT_CHANGED", "DEVICE_ENDPOINT_REVOKED"):
        policy = ACTION_POLICIES[action]
        assert policy.publishers == frozenset({"notification-service"})
        assert policy.resource_types == frozenset({"device_endpoint"})
        assert policy.reference_types == frozenset({"endpoint_id"})
