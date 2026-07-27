"""Versioned action and controlled-change allowlists for AuditEventV1."""

from __future__ import annotations

from dataclasses import dataclass

from audit_log_service.domain.errors import AuditError
from audit_log_service.domain.models import AuditEvent, AuditResult

APPROVED_PUBLISHERS = frozenset(
    {
        "api-gateway",
        "identity-service",
        "school-service",
        "consent-service",
        "camera-registry-service",
        "ansvis-adapter-service",
        "event-ingestion-service",
        "attendance-service",
        "timekeeping-service",
        "violation-service",
        "evidence-storage-service",
        "notification-service",
        "report-service",
        "ai-model-registry-service",
        "key-management-service",
        "retention-worker",
        "backup-service",
        "audit-log-service",
    }
)

REFERENCE_RESOURCE_TYPES = frozenset(
    {
        "ansvis_source",
        "ansvis_task",
        "audit_partition",
        "backup_restore",
        "key",
        "retention_job",
        "retention_policy",
    }
)


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    publishers: frozenset[str]
    resource_types: frozenset[str]
    results: frozenset[AuditResult]
    purpose_required: bool = False
    school_scope_required: bool = True
    resource_identity_required: bool = True
    changed_fields: frozenset[str] = frozenset()
    reference_types: frozenset[str] = frozenset()
    count_names: frozenset[str] = frozenset()
    policy_types: frozenset[str] = frozenset()


def _expected_result(action: str) -> AuditResult:
    if action.endswith("_DENIED") or action.endswith("_REJECTED"):
        return AuditResult.DENIED
    if action.endswith("_FAILED") or action.endswith("_DEAD_LETTERED"):
        return AuditResult.FAILED
    if action == "RETENTION_JOB_BLOCKED":
        return AuditResult.FAILED
    return AuditResult.SUCCESS


def _policies(
    actions: tuple[str, ...],
    *,
    publishers: tuple[str, ...],
    resources: tuple[str, ...],
    purpose: bool = False,
    school: bool = True,
    identity: bool = True,
    fields: tuple[str, ...] = (),
    references: tuple[str, ...] = (),
    counts: tuple[str, ...] = (),
    versions: tuple[str, ...] = (),
) -> dict[str, ActionPolicy]:
    return {
        action: ActionPolicy(
            publishers=frozenset(publishers),
            resource_types=frozenset(resources),
            results=frozenset({_expected_result(action)}),
            purpose_required=purpose,
            school_scope_required=school,
            resource_identity_required=identity,
            changed_fields=frozenset(fields),
            reference_types=frozenset(references),
            count_names=frozenset(counts),
            policy_types=frozenset(versions),
        )
        for action in actions
    }


ACTION_POLICIES: dict[str, ActionPolicy] = {}

ACTION_POLICIES.update(
    _policies(
        ("AUTH_LOGIN_SUCCEEDED", "AUTH_LOGIN_FAILED"),
        publishers=("api-gateway", "identity-service"),
        resources=("user", "session"),
        identity=False,
    )
)
ACTION_POLICIES.update(
    _policies(
        ("SESSION_REVOKED",),
        publishers=("identity-service",),
        resources=("session",),
        fields=("status",),
        references=("session_id",),
        versions=("session_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("MFA_CHANGED",),
        publishers=("identity-service",),
        resources=("mfa_factor", "user"),
        fields=("factor_type", "status"),
        references=("mfa_factor_id",),
        versions=("mfa_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("ROLE_ASSIGNMENT_CHANGED",),
        publishers=("identity-service",),
        resources=("role_assignment",),
        fields=("role_code", "scope_type", "status", "validity"),
        references=("role_id", "scope_id", "user_id"),
        versions=("rbac_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("PERMISSION_CHANGED",),
        publishers=("identity-service",),
        resources=("permission",),
        fields=("action", "requires_audit", "requires_object_scope", "resource", "status"),
        references=("permission_id",),
        versions=("rbac_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        (
            "SENSITIVE_PROFILE_VIEW_GRANTED",
            "SENSITIVE_PROFILE_VIEW_DENIED",
            "SENSITIVE_PROFILE_EXPORTED",
        ),
        publishers=("api-gateway", "identity-service", "school-service", "report-service"),
        resources=("profile", "student", "guardian", "staff"),
        purpose=True,
        references=("export_id",),
        counts=("record_count",),
        versions=("rbac_policy", "retention_policy"),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("SENSITIVE_PROFILE_UPDATED",),
        publishers=("school-service",),
        resources=("profile", "student", "guardian", "staff"),
        purpose=True,
        fields=("biometric_subject_ref", "contact", "date_of_birth", "full_name", "status"),
        versions=("rbac_policy", "retention_policy"),
    )
)

ACTION_POLICIES.update(
    _policies(
        (
            "CONSENT_REQUESTED",
            "CONSENT_GRANTED",
            "CONSENT_DENIED",
            "CONSENT_WITHDRAWN",
            "CONSENT_EXPIRED",
            "CONSENT_RESTRICTED",
        ),
        publishers=("consent-service",),
        resources=("consent",),
        purpose=True,
        fields=("status", "validity", "scope"),
        references=("consent_id", "subject_id"),
        versions=("consent_policy", "retention_policy"),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("CONSENT_CHECK_DENIED",),
        publishers=("consent-service",),
        resources=("consent", "subject"),
        purpose=True,
        versions=("consent_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("SUBJECT_REQUEST_STATUS_CHANGED",),
        publishers=("consent-service",),
        resources=("subject_request",),
        purpose=True,
        fields=("request_type", "status"),
        references=("request_id", "subject_id"),
        versions=("privacy_policy", "retention_policy"),
    )
)

ACTION_POLICIES.update(
    _policies(
        ("ANSVIS_SOURCE_AUTH_DENIED",),
        publishers=("api-gateway", "ansvis-adapter-service"),
        resources=("ansvis_source",),
        school=False,
        identity=False,
        references=("source_id",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("CAMERA_MAPPING_CHANGED",),
        publishers=("camera-registry-service",),
        resources=("camera", "camera_zone"),
        purpose=True,
        fields=(
            "ansvis_source",
            "config",
            "metadata",
            "purpose",
            "schedule",
            "status",
            "task",
            "zone",
        ),
        references=("camera_id", "source_id", "task_id", "zone_id"),
        versions=("camera_mapping",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("ANSVIS_TASK_CONFIG_CHANGED",),
        publishers=("ansvis-adapter-service", "camera-registry-service"),
        resources=("ansvis_task",),
        fields=("config", "model", "roi", "schedule", "status", "threshold"),
        references=("task_id",),
        versions=("config", "model", "roi", "schedule", "threshold"),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("EVENT_PROCESSING_DEAD_LETTERED",),
        publishers=("event-ingestion-service",),
        resources=("event",),
        references=("event_id", "outbox_id"),
        counts=("attempt_count",),
        versions=("event_contract",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("EVENT_CONSENT_DENIED",),
        publishers=("event-ingestion-service",),
        resources=("event", "ingestion_receipt"),
        references=("event_id", "receipt_id", "outbox_id"),
        versions=("consent_policy",),
    )
)

for prefix, publisher, resource in (
    ("ATTENDANCE", "attendance-service", "attendance_record"),
    ("TIMEKEEPING", "timekeeping-service", "timekeeping_record"),
):
    ACTION_POLICIES.update(
        _policies(
            (
                f"{prefix}_VIEW_GRANTED",
                f"{prefix}_VIEW_DENIED",
                f"{prefix}_EXPORTED",
            ),
            publishers=(publisher, "report-service"),
            resources=(resource,),
            purpose=True,
            references=("export_id",),
            counts=("record_count",),
            versions=("rbac_policy", "retention_policy"),
        )
    )
    ACTION_POLICIES.update(
        _policies(
            (f"{prefix}_CORRECTION_SUBMITTED", f"{prefix}_CORRECTION_DECIDED"),
            publishers=(publisher,),
            resources=(resource, f"{resource}_correction"),
            purpose=True,
            fields=("correction_status", "status"),
            references=("correction_id", "record_id"),
            versions=("correction_policy", "rbac_policy"),
        )
    )

ACTION_POLICIES.update(
    _policies(
        ("VIOLATION_VIEW_GRANTED", "VIOLATION_VIEW_DENIED", "VIOLATION_EXPORTED"),
        publishers=("violation-service", "report-service"),
        resources=("violation",),
        purpose=True,
        references=("export_id",),
        counts=("record_count",),
        versions=("rbac_policy", "retention_policy"),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("VIOLATION_REVIEW_DECIDED", "VIOLATION_APPEAL_STATUS_CHANGED"),
        publishers=("violation-service",),
        resources=("violation", "violation_appeal", "violation_review"),
        purpose=True,
        fields=("appeal_status", "review_status", "status"),
        references=("appeal_id", "review_id", "violation_id"),
        versions=("appeal_policy", "review_policy"),
    )
)

ACTION_POLICIES.update(
    _policies(
        (
            "EVIDENCE_UPLOAD_REQUESTED",
            "EVIDENCE_UPLOAD_FINALIZED",
            "EVIDENCE_UPLOAD_REJECTED",
            "EVIDENCE_VIEW_GRANTED",
            "EVIDENCE_VIEW_DENIED",
            "EVIDENCE_EXPORT_GRANTED",
            "EVIDENCE_EXPORT_DENIED",
            "EVIDENCE_DELETE_REQUESTED",
            "EVIDENCE_DELETE_COMPLETED",
            "EVIDENCE_DELETE_FAILED",
            "EVIDENCE_ORPHAN_RECONCILED",
        ),
        publishers=("evidence-storage-service",),
        resources=("evidence",),
        purpose=True,
        fields=("availability", "retention_state", "status"),
        references=("evidence_id", "resource_id"),
        counts=("object_count", "orphan_count"),
        versions=("evidence_policy", "retention_policy"),
    )
)

ACTION_POLICIES.update(
    _policies(
        ("NOTIFICATION_RECIPIENT_DENIED",),
        publishers=("notification-service",),
        resources=("notification_recipient",),
        purpose=True,
        references=("notification_id", "recipient_id"),
        versions=("notification_policy", "rbac_policy"),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("DEVICE_ENDPOINT_CHANGED",),
        publishers=("notification-service",),
        resources=("device_endpoint",),
        fields=("provider", "status"),
        references=("endpoint_id",),
        versions=("notification_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("REPORT_EXPORT_REQUESTED", "REPORT_EXPORT_DOWNLOADED", "REPORT_EXPORT_EXPIRED"),
        publishers=("report-service",),
        resources=("report_export",),
        purpose=True,
        fields=("status",),
        references=("export_id", "report_job_id"),
        counts=("record_count",),
        versions=("rbac_policy", "report_policy", "retention_policy"),
    )
)

ACTION_POLICIES.update(
    _policies(
        ("DATASET_APPROVAL_CHANGED",),
        publishers=("ai-model-registry-service",),
        resources=("dataset",),
        fields=("approval_status", "status"),
        references=("dataset_id",),
        versions=("dataset_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("MODEL_APPROVAL_CHANGED",),
        publishers=("ai-model-registry-service",),
        resources=("model",),
        fields=("approval_status", "status"),
        references=("model_id",),
        versions=("model_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("MODEL_DEPLOYMENT_CHANGED",),
        publishers=("ai-model-registry-service",),
        resources=("model_deployment",),
        fields=("deployment_status", "status"),
        references=("deployment_id", "model_id"),
        versions=("model", "pipeline"),
    )
)

KEY_ACTIONS = (
    "KEY_CREATED",
    "KEY_ACTIVATED",
    "KEY_POLICY_CHANGED",
    "KEY_ROTATION_STARTED",
    "KEY_ALIAS_SWITCHED",
    "KEY_REWRAP_PROGRESS",
    "KEY_ROTATION_COMPLETED",
    "KEY_ROTATION_FAILED",
    "KEY_DISABLED",
    "KEY_REENABLED",
    "KEY_COMPROMISE_DECLARED",
    "KEY_RECOVERY_ACCESSED",
    "KEY_DESTROY_SCHEDULED",
    "KEY_DESTROY_CANCELLED",
    "KEY_DESTROY_COMPLETED",
)
ACTION_POLICIES.update(
    _policies(
        KEY_ACTIONS,
        publishers=("key-management-service",),
        resources=("key",),
        school=False,
        fields=("key_state", "policy", "status"),
        references=("change_id", "key_id", "rotation_id"),
        counts=("eligible_count", "processed_count", "remaining_count"),
        versions=("key_policy",),
    )
)

RETENTION_ACTIONS = (
    "RETENTION_POLICY_ACTIVATED",
    "RETENTION_DRY_RUN_COMPLETED",
    "RETENTION_JOB_APPROVED",
    "RETENTION_JOB_BLOCKED",
    "RETENTION_DELETE_STARTED",
    "RETENTION_DELETE_COMPLETED",
    "RETENTION_DELETE_FAILED",
    "ANONYMIZATION_COMPLETED",
    "LEGAL_HOLD_CHANGED",
)
ACTION_POLICIES.update(
    _policies(
        RETENTION_ACTIONS,
        publishers=("retention-worker",),
        resources=("legal_hold", "retention_job", "retention_policy"),
        school=False,
        fields=("hold_status", "job_status", "policy_status", "status"),
        references=("approval_id", "hold_id", "job_id", "policy_id"),
        counts=(
            "already_absent_count",
            "eligible_count",
            "failed_count",
            "held_count",
            "processed_count",
            "remaining_count",
        ),
        versions=("retention_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("BACKUP_RESTORE_STARTED", "BACKUP_RESTORE_COMPLETED", "BACKUP_RESTORE_FAILED"),
        publishers=("backup-service",),
        resources=("backup_restore",),
        school=False,
        fields=("restore_status", "status"),
        references=("restore_id", "snapshot_id"),
        counts=("reapplied_tombstone_count", "restored_object_count"),
        versions=("backup_policy", "retention_policy"),
    )
)

ACTION_POLICIES.update(
    _policies(
        (
            "AUDIT_QUERY_GRANTED",
            "AUDIT_QUERY_DENIED",
            "AUDIT_EXPORT_GRANTED",
            "AUDIT_EXPORT_DENIED",
        ),
        publishers=("audit-log-service",),
        resources=("audit_export", "audit_query"),
        purpose=True,
        school=False,
        references=("export_id", "query_id"),
        counts=("record_count",),
        versions=("audit_access_policy", "retention_policy"),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("AUDIT_INTEGRITY_FAILED",),
        publishers=("audit-log-service",),
        resources=("audit_partition",),
        school=False,
        references=("checkpoint_id", "partition_id"),
        counts=("failure_count",),
        versions=("integrity_policy",),
    )
)
ACTION_POLICIES.update(
    _policies(
        ("AUDIT_POLICY_CHANGED",),
        publishers=("audit-log-service",),
        resources=("audit_policy",),
        school=False,
        fields=("policy_status", "status"),
        references=("policy_id",),
        versions=("audit_access_policy", "integrity_policy", "retention_policy"),
    )
)

APPROVED_ACTIONS = frozenset(ACTION_POLICIES)


def validate_action_policy(event: AuditEvent) -> None:
    """Fail closed on unknown action/source/schema combinations and change summaries."""

    policy = ACTION_POLICIES.get(event.action)
    if policy is None:
        raise AuditError("AUDIT_ACTION_UNKNOWN")
    if event.source_service not in APPROVED_PUBLISHERS:
        raise AuditError("AUDIT_EVENT_INVALID")
    if event.source_service not in policy.publishers:
        raise AuditError("AUDIT_EVENT_INVALID")
    if event.resource_type not in policy.resource_types or event.result not in policy.results:
        raise AuditError("AUDIT_EVENT_INVALID")
    if policy.purpose_required and event.purpose_code is None:
        raise AuditError("AUDIT_EVENT_INVALID")
    if policy.school_scope_required and event.school_id is None:
        raise AuditError("AUDIT_EVENT_INVALID")
    if (
        policy.resource_identity_required
        and event.resource_id is None
        and event.resource_ref is None
    ):
        raise AuditError("AUDIT_EVENT_INVALID")
    if event.resource_ref is not None and event.resource_type not in REFERENCE_RESOURCE_TYPES:
        raise AuditError("AUDIT_EVENT_INVALID")

    changes = event.changes
    if not set(changes.changed_fields).issubset(policy.changed_fields):
        raise AuditError("AUDIT_CHANGE_FORBIDDEN")
    before_fields = {field for field, _ in changes.state_before_codes}
    after_fields = {field for field, _ in changes.state_after_codes}
    if not before_fields.issubset(policy.changed_fields):
        raise AuditError("AUDIT_CHANGE_FORBIDDEN")
    if not after_fields.issubset(policy.changed_fields):
        raise AuditError("AUDIT_CHANGE_FORBIDDEN")
    if not {name for name, _ in changes.reference_ids}.issubset(policy.reference_types):
        raise AuditError("AUDIT_CHANGE_FORBIDDEN")
    if not {name for name, _ in changes.count_summary}.issubset(policy.count_names):
        raise AuditError("AUDIT_CHANGE_FORBIDDEN")
    if not {name for name, _ in changes.policy_versions}.issubset(policy.policy_types):
        raise AuditError("AUDIT_CHANGE_FORBIDDEN")
