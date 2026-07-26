from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = Path("packages/consent-withdrawal-policy/consent-withdrawal-policy-v1.json")
FIXTURE_PATH = Path(
    "packages/test-fixtures/consent-withdrawal/consent-withdrawal-policy-cases.synthetic.json"
)

WITHDRAWAL_POLICY_INVALID = "WITHDRAWAL_POLICY_INVALID"
WITHDRAWAL_FIXTURE_INVALID = "WITHDRAWAL_FIXTURE_INVALID"
CASE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")

EXPECTED_OPERATIONS = {
    "request",
    "verify_identity",
    "make_effective",
    "processing_access",
    "propagate",
    "acknowledge",
    "reconcile",
    "complete",
    "reject",
    "supersede",
}
EXPECTED_STATES = {
    "requested",
    "identity_verified",
    "effective",
    "propagating",
    "partially_completed",
    "completed",
    "rejected",
    "superseded",
}
EXPECTED_TRANSITIONS = {
    "requested": {"identity_verified", "rejected", "superseded"},
    "identity_verified": {"effective", "rejected", "superseded"},
    "effective": {
        "propagating",
        "partially_completed",
        "completed",
        "superseded",
    },
    "propagating": {"partially_completed", "completed", "superseded"},
    "partially_completed": {"propagating", "completed", "superseded"},
    "completed": {"superseded"},
    "rejected": {"superseded"},
    "superseded": set(),
}
EXPECTED_DENY_STATES = {
    "effective",
    "propagating",
    "partially_completed",
    "completed",
    "superseded",
}
EXPECTED_REASON_TAXONOMY = {
    "subject_request",
    "guardian_request",
    "purpose_ended",
    "consent_invalidated",
    "authority_corrected",
    "duplicate_replay",
    "request_rejected",
    "policy_superseded",
}
EXPECTED_DISPOSITIONS = {
    "deactivate",
    "unlink_identity",
    "delete_exact_media_or_reference",
    "anonymize_approved_fields",
    "retain_restricted_proof",
    "preserve_approved_anonymous_aggregate",
}

EXPECTED_AUTHORITIES: dict[str, dict[str, object]] = {
    "student_self": {
        "relationships": {"own_student_subject"},
        "permission_code": "privacy.withdrawal.request.self",
        "maturity_authority_review": "required",
        "allowed_subject_types": {"student"},
    },
    "parent_guardian": {
        "relationships": {"active_verified_guardian_of_subject"},
        "permission_code": "privacy.withdrawal.request.guardian",
        "maturity_authority_review": "required",
        "allowed_subject_types": {"student"},
    },
    "staff_self": {
        "relationships": {"own_staff_subject"},
        "permission_code": "privacy.withdrawal.request.self",
        "maturity_authority_review": "not_required",
        "allowed_subject_types": {"staff"},
    },
    "privacy_officer": {
        "relationships": {"approved_privacy_case_delegation"},
        "permission_code": "privacy.withdrawal.request.delegated",
        "maturity_authority_review": "required_for_student",
        "allowed_subject_types": {"student", "staff"},
    },
    "service_orchestrator": {
        "relationships": {"approved_service_delegation"},
        "permission_code": "service.privacy.withdrawal.orchestrate",
        "maturity_authority_review": "decision_must_be_preverified",
        "allowed_subject_types": {"student", "staff"},
    },
}

EXPECTED_STORES: dict[str, tuple[str, str, str, str, str, str, str, str]] = {
    "privacy_consent_record": (
        "privacy_service",
        "Critical",
        "record_effective_and_deny_processing",
        "retain_restricted_proof",
        "approved_consent_proof_retention_rule",
        "privacy_owner_ack",
        "opaque_withdrawal_version_and_outcome",
        "retain_exact_restricted_proof_without_access_grant",
    ),
    "identity_biometric_reference": (
        "identity_service",
        "Critical",
        "deactivate_and_block_biometric_lookup",
        "unlink_identity",
        "approved_identity_unlink_rule",
        "identity_owner_ack",
        "opaque_reference_unlinked_count",
        "pause_physical_disposition_only",
    ),
    "ansvis_face_enrollment": (
        "ansvis_adapter",
        "Critical",
        "disable_recognition_and_enrollment_mapping",
        "delete_exact_media_or_reference",
        "approved_ansvis_enrollment_owner_and_provider_action",
        "ansvis_owner_ack",
        "opaque_provider_action_outcome",
        "pause_exact_provider_disposition_only",
    ),
    "ansvis_task_subject_mapping": (
        "ansvis_adapter",
        "Critical",
        "remove_subject_from_task_scope",
        "unlink_identity",
        "approved_ansvis_task_mapping_rule",
        "ansvis_owner_ack",
        "opaque_mapping_unlinked_count",
        "hold_never_keeps_active_task_mapping",
    ),
    "attendance_identity_link": (
        "attendance_service",
        "High_or_Critical",
        "deny_future_biometric_event_identity_use",
        "unlink_identity",
        "approved_attendance_subject_link_rule",
        "attendance_owner_ack",
        "opaque_link_action_count",
        "retain_business_record_restricted_without_biometric_link",
    ),
    "timekeeping_identity_link": (
        "timekeeping_service",
        "High_or_Critical",
        "deny_future_biometric_event_identity_use",
        "unlink_identity",
        "approved_timekeeping_subject_link_rule",
        "timekeeping_owner_ack",
        "opaque_link_action_count",
        "retain_business_record_restricted_without_biometric_link",
    ),
    "violation_subject_link": (
        "violation_service",
        "High_or_Critical",
        "deny_withdrawn_purpose_use_and_subject_access",
        "anonymize_approved_fields",
        "approved_violation_anonymization_field_set",
        "violation_owner_ack",
        "opaque_anonymization_action_count",
        "pause_exact_field_disposition_without_access_grant",
    ),
    "private_evidence_object": (
        "evidence_service",
        "High_or_Critical",
        "deny_view_decrypt_signed_url_and_export",
        "delete_exact_media_or_reference",
        "approved_evidence_object_disposition_rule",
        "evidence_owner_ack",
        "opaque_object_action_and_count",
        "pause_exact_object_disposition_without_access_grant",
    ),
    "notification_pending_or_retry": (
        "notification_service",
        "High",
        "cancel_subject_linked_delivery_and_open",
        "deactivate",
        "active_notification_cancellation_contract",
        "notification_owner_ack",
        "opaque_cancelled_delivery_count",
        "hold_never_preserves_delivery_authority",
    ),
    "report_export_artifact": (
        "reporting_service",
        "High_or_Critical",
        "deny_generation_download_and_reuse",
        "delete_exact_media_or_reference",
        "approved_export_artifact_disposition_rule",
        "reporting_owner_ack",
        "opaque_export_action_count",
        "pause_exact_artifact_disposition_without_access_grant",
    ),
    "cache_entry": (
        "owning_service",
        "High_or_Critical",
        "invalidate_before_next_read_or_processing",
        "delete_exact_media_or_reference",
        "versioned_cache_invalidation_contract",
        "cache_owner_ack",
        "opaque_cache_generation_and_count",
        "hold_never_preserves_cache_access",
    ),
    "queue_or_dead_letter_envelope": (
        "owning_service",
        "High_minimized",
        "cancel_or_tombstone_subject_linked_work",
        "deactivate",
        "versioned_queue_cancellation_contract",
        "queue_owner_ack",
        "opaque_cancelled_work_count",
        "hold_never_preserves_processing_authority",
    ),
    "read_model": (
        "reporting_service",
        "High_or_Critical",
        "deny_stale_read_and_rebuild_without_subject_link",
        "anonymize_approved_fields",
        "approved_read_model_anonymization_field_set",
        "read_model_owner_ack",
        "opaque_rebuild_version_and_count",
        "pause_exact_disposition_without_read_access",
    ),
    "backup_restore_reapplication_index": (
        "backup_restore_owner",
        "High_minimized",
        "reapply_deny_and_disposition_after_restore",
        "retain_restricted_proof",
        "approved_backup_restore_reconciliation_contract",
        "backup_restore_owner_ack",
        "opaque_restore_checkpoint_and_outcome",
        "hold_scope_reapplied_without_access_grant",
    ),
    "approved_anonymous_aggregate": (
        "reporting_service",
        "Medium_or_High",
        "prove_irreversible_subject_unlinking",
        "preserve_approved_anonymous_aggregate",
        "approved_anonymization_field_set_and_reidentification_review",
        "reporting_owner_ack",
        "aggregate_policy_version_and_count_only",
        "hold_not_required_after_approved_irreversible_anonymization",
    ),
}

EXPECTED_REASON_CODES = {
    "request_allowed": "WITHDRAWAL_REQUEST_ALLOWED",
    "identity_verification_allowed": "WITHDRAWAL_IDENTITY_VERIFICATION_ALLOWED",
    "effective_allowed": "WITHDRAWAL_EFFECTIVE_ALLOWED",
    "propagation_allowed": "WITHDRAWAL_PROPAGATION_ALLOWED",
    "acknowledgement_allowed": "WITHDRAWAL_ACKNOWLEDGEMENT_ALLOWED",
    "reconciliation_allowed": "WITHDRAWAL_RECONCILIATION_ALLOWED",
    "completion_allowed": "WITHDRAWAL_COMPLETION_ALLOWED",
    "rejection_allowed": "WITHDRAWAL_REJECTION_ALLOWED",
    "supersession_allowed": "WITHDRAWAL_SUPERSESSION_ALLOWED",
    "duplicate_replayed": "WITHDRAWAL_DUPLICATE_REPLAYED",
    "processing_denied": "WITHDRAWAL_PROCESSING_DENIED",
    "processing_requires_separate_authorization": (
        "WITHDRAWAL_SEPARATE_PROCESSING_AUTHORIZATION_REQUIRED"
    ),
    "policy_inactive": "WITHDRAWAL_POLICY_INACTIVE",
    "runtime_approval_missing": "WITHDRAWAL_RUNTIME_APPROVAL_MISSING",
    "change_record_required": "WITHDRAWAL_CHANGE_RECORD_REQUIRED",
    "actor_unauthenticated": "WITHDRAWAL_ACTOR_UNAUTHENTICATED",
    "actor_authority_denied": "WITHDRAWAL_ACTOR_AUTHORITY_DENIED",
    "relationship_denied": "WITHDRAWAL_RELATIONSHIP_DENIED",
    "maturity_authority_ambiguous": "WITHDRAWAL_MATURITY_AUTHORITY_AMBIGUOUS",
    "scope_denied": "WITHDRAWAL_SCOPE_DENIED",
    "purpose_denied": "WITHDRAWAL_PURPOSE_DENIED",
    "identity_not_verified": "WITHDRAWAL_IDENTITY_NOT_VERIFIED",
    "reason_denied": "WITHDRAWAL_REASON_DENIED",
    "idempotency_denied": "WITHDRAWAL_IDEMPOTENCY_DENIED",
    "version_stale": "WITHDRAWAL_VERSION_STALE",
    "transition_denied": "WITHDRAWAL_TRANSITION_DENIED",
    "correction_overwrite_denied": "WITHDRAWAL_CORRECTION_OVERWRITE_DENIED",
    "deny_before_dispose_missing": "WITHDRAWAL_DENY_BEFORE_DISPOSE_MISSING",
    "owner_scope_denied": "WITHDRAWAL_OWNER_SCOPE_DENIED",
    "disposition_denied": "WITHDRAWAL_DISPOSITION_DENIED",
    "activation_dependency_missing": "WITHDRAWAL_ACTIVATION_DEPENDENCY_MISSING",
    "owner_acknowledgement_missing": "WITHDRAWAL_OWNER_ACKNOWLEDGEMENT_MISSING",
    "dependency_unavailable": "WITHDRAWAL_DEPENDENCY_UNAVAILABLE",
    "legal_hold_scope_invalid": "WITHDRAWAL_LEGAL_HOLD_SCOPE_INVALID",
    "disposition_paused_legal_hold": ("WITHDRAWAL_DISPOSITION_PAUSED_LEGAL_HOLD"),
    "lawful_basis_scope_invalid": "WITHDRAWAL_LAWFUL_BASIS_SCOPE_INVALID",
    "restricted_retention_required": "WITHDRAWAL_RESTRICTED_RETENTION_REQUIRED",
    "checkpoint_invalid": "WITHDRAWAL_CHECKPOINT_INVALID",
    "reconciliation_unbounded": "WITHDRAWAL_RECONCILIATION_UNBOUNDED",
    "partial_failure_open": "WITHDRAWAL_PARTIAL_FAILURE_OPEN",
    "restore_reapply_pending": "WITHDRAWAL_RESTORE_REAPPLY_PENDING",
    "completion_evidence_invalid": "WITHDRAWAL_COMPLETION_EVIDENCE_INVALID",
}
EXPECTED_PUBLIC_ERRORS = {
    "concealed": "WITHDRAWAL_REQUEST_NOT_FOUND",
    "invalid": "WITHDRAWAL_REQUEST_INVALID",
    "conflict": "WITHDRAWAL_REQUEST_CONFLICT",
    "pending": "WITHDRAWAL_PROCESSING_PENDING",
    "dependency_unavailable": "WITHDRAWAL_SERVICE_UNAVAILABLE",
}
EXPECTED_COMPLETION_REQUIRED = {
    "policy_id",
    "policy_version",
    "opaque_withdrawal_ref",
    "opaque_subject_ref",
    "opaque_resource_ref",
    "canonical_owner",
    "disposition",
    "outcome",
    "stable_reason_code",
    "resource_count",
    "started_at",
    "completed_at",
    "opaque_approver_ref",
    "correlation_id",
}
EXPECTED_COMPLETION_OPTIONAL = {
    "checkpoint_ref",
    "retry_count",
    "hold_ref",
    "lawful_basis_ref",
    "next_reconciliation_at",
}
EXPECTED_FORBIDDEN_FIELDS = {
    "subject_name",
    "guardian_name",
    "student_code",
    "staff_code",
    "email_address",
    "phone_number",
    "personal_before_value",
    "personal_after_value",
    "consent_free_text",
    "biometric_reference",
    "face_embedding",
    "face_image",
    "media_binary",
    "image_base64",
    "signed_url",
    "bucket_name",
    "object_key",
    "provider_identifier",
    "device_token",
    "credential",
    "raw_ansvis_payload",
    "database_row",
    "backup_content",
    "free_form_note",
}
EXPECTED_AUDIT_ACTIONS = {
    "CONSENT_WITHDRAWAL_REQUESTED",
    "CONSENT_WITHDRAWAL_IDENTITY_VERIFIED",
    "CONSENT_WITHDRAWAL_EFFECTIVE",
    "CONSENT_WITHDRAWAL_PROPAGATION_STARTED",
    "CONSENT_WITHDRAWAL_OWNER_ACKNOWLEDGED",
    "CONSENT_WITHDRAWAL_PARTIALLY_COMPLETED",
    "CONSENT_WITHDRAWAL_COMPLETED",
    "CONSENT_WITHDRAWAL_REJECTED",
    "CONSENT_WITHDRAWAL_SUPERSEDED",
    "CONSENT_WITHDRAWAL_RECONCILIATION_SCHEDULED",
    "CONSENT_WITHDRAWAL_RESTORE_REAPPLIED",
    "CONSENT_WITHDRAWAL_PROCESSING_DENIED",
    "CONSENT_WITHDRAWAL_DISPOSITION_PAUSED",
}
EXPECTED_AUDIT_REQUIRED = {
    "opaque_actor_or_service_ref",
    "opaque_subject_ref",
    "tenant_ref",
    "school_ref",
    "opaque_withdrawal_ref",
    "withdrawal_version",
    "purpose_code",
    "action",
    "outcome",
    "stable_reason_code",
    "request_id",
    "correlation_id",
    "occurred_at",
}
EXPECTED_AUDIT_OPTIONAL = {
    "canonical_owner",
    "store_class",
    "disposition",
    "opaque_resource_ref",
    "resource_count",
    "checkpoint_ref",
}
EXPECTED_HOLD_INPUTS = {
    "approved_hold_authority",
    "exact_object_scope",
    "exact_purpose",
    "reason_code",
    "effective_at",
    "review_or_expiry_at",
    "approver",
    "audit_reference",
}
EXPECTED_BASIS_INPUTS = {
    "basis_code",
    "exact_object_scope",
    "exact_purpose",
    "canonical_owner",
    "active_version",
    "effective_at",
    "review_or_expiry_at",
    "approver",
    "audit_reference",
}
EXPECTED_METRICS = {
    "withdrawal_effective_total",
    "withdrawal_owner_ack_pending",
    "withdrawal_partial_failure_total",
    "withdrawal_reconciliation_lag",
    "withdrawal_restore_reapply_pending",
    "withdrawal_completion_age",
}
EXPECTED_SUPERSESSION_TRIGGERS = {
    "state_or_transition_change",
    "actor_authority_or_maturity_change",
    "reason_or_disposition_change",
    "owner_store_or_completion_evidence_change",
    "legal_hold_or_lawful_basis_change",
    "retry_reconciliation_or_restore_change",
    "audit_or_error_change",
    "customer_legal_privacy_or_security_finding",
    "runtime_activation_change",
}
EXPECTED_SUPERSESSION_EVIDENCE = {
    "owner_disposition_matrix",
    "synthetic_compatibility_matrix",
    "privacy_legal_approval",
    "security_ops_approval",
    "business_owner_approval",
    "affected_store_owner_approvals",
    "rollback_and_supersession_record",
}

CONTEXT_FIELDS = {
    "operation",
    "policy_version_status",
    "runtime_approval_status",
    "destructive_change_record_status",
    "actor_authenticated",
    "actor_role",
    "actor_permission_code",
    "actor_relationship",
    "subject_type",
    "maturity_authority_status",
    "tenant_scope_match",
    "school_scope_match",
    "subject_scope_match",
    "purpose_code",
    "purpose_status",
    "actor_identity_status",
    "subject_identity_status",
    "reason_code",
    "idempotency_status",
    "request_version_status",
    "current_state",
    "transition_to",
    "correction_overwrites_effective",
    "deny_committed_before_disposal",
    "store_class",
    "canonical_owner",
    "disposition",
    "activation_dependency_status",
    "owner_acknowledgement_status",
    "all_required_owner_acknowledged",
    "dependency_available",
    "destructive_execution_requested",
    "physical_disposition_requested",
    "legal_hold_active",
    "legal_hold_scope_status",
    "legal_hold_authority_status",
    "lawful_basis_active",
    "lawful_basis_scope_status",
    "lawful_basis_purpose_status",
    "lawful_basis_owner_status",
    "lawful_basis_version_status",
    "restricted_retention_applied",
    "checkpoint_status",
    "reconciliation_status",
    "partial_failure_open",
    "restore_reapply_pending",
    "restore_reapply_authorized",
    "completion_evidence_fields",
    "superseding_version_linked",
}
BOOLEAN_CONTEXT_FIELDS = {
    "actor_authenticated",
    "tenant_scope_match",
    "school_scope_match",
    "subject_scope_match",
    "correction_overwrites_effective",
    "deny_committed_before_disposal",
    "all_required_owner_acknowledged",
    "dependency_available",
    "destructive_execution_requested",
    "physical_disposition_requested",
    "legal_hold_active",
    "lawful_basis_active",
    "restricted_retention_applied",
    "partial_failure_open",
    "restore_reapply_pending",
    "restore_reapply_authorized",
    "superseding_version_linked",
}


class WithdrawalPolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AuthorityPolicy:
    relationships: frozenset[str]
    permission_code: str
    maturity_review: str
    subject_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class StorePolicy:
    canonical_owner: str
    disposition: str


@dataclass(frozen=True, slots=True)
class WithdrawalPolicy:
    version: int
    operations: frozenset[str]
    states: frozenset[str]
    transitions: dict[str, frozenset[str]]
    deny_states: frozenset[str]
    authorities: dict[str, AuthorityPolicy]
    stores: dict[str, StorePolicy]
    reasons: frozenset[str]
    dispositions: frozenset[str]
    reason_codes: dict[str, str]
    public_errors: dict[str, str]
    completion_required: frozenset[str]
    completion_optional: frozenset[str]
    completion_forbidden: frozenset[str]


@dataclass(frozen=True, slots=True)
class Decision:
    decision: str
    reason_code: str
    public_error: str


def _fail(code: str, detail: str) -> NoReturn:
    raise WithdrawalPolicyError(f"{code}: {detail}")


def _mapping(value: object, *, code: str, location: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(code, f"{location} must be an object with string keys")
    return cast(dict[str, object], value)


def _text(value: object, *, code: str, location: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(code, f"{location} must be non-empty text")
    return value


def _boolean(value: object, *, code: str, location: str) -> bool:
    if not isinstance(value, bool):
        _fail(code, f"{location} must be boolean")
    return value


def _integer(value: object, *, code: str, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(code, f"{location} must be an integer")
    return value


def _text_set(value: object, *, code: str, location: str) -> set[str]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
        or len(value) != len(set(value))
    ):
        _fail(code, f"{location} must be a unique non-empty text list")
    return set(cast(list[str], value))


def _expect_keys(
    value: dict[str, object],
    expected: set[str],
    *,
    code: str,
    location: str,
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            code,
            f"{location} keys differ: missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}",
        )


def _expect_exact(value: object, expected: object, *, location: str) -> None:
    if value != expected:
        _fail(WITHDRAWAL_POLICY_INVALID, f"{location} differs from immutable v1")


def _validate_authorities(value: object) -> dict[str, AuthorityPolicy]:
    document = _mapping(value, code=WITHDRAWAL_POLICY_INVALID, location="authority_matrix")
    _expect_keys(
        document,
        set(EXPECTED_AUTHORITIES),
        code=WITHDRAWAL_POLICY_INVALID,
        location="authority_matrix",
    )
    result: dict[str, AuthorityPolicy] = {}
    for role, expected in EXPECTED_AUTHORITIES.items():
        item = _mapping(
            document[role],
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"authority_matrix.{role}",
        )
        _expect_keys(
            item,
            {
                "relationships",
                "permission_code",
                "maturity_authority_review",
                "allowed_subject_types",
            },
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"authority_matrix.{role}",
        )
        relationships = _text_set(
            item["relationships"],
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"authority_matrix.{role}.relationships",
        )
        subject_types = _text_set(
            item["allowed_subject_types"],
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"authority_matrix.{role}.allowed_subject_types",
        )
        permission = _text(
            item["permission_code"],
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"authority_matrix.{role}.permission_code",
        )
        maturity = _text(
            item["maturity_authority_review"],
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"authority_matrix.{role}.maturity_authority_review",
        )
        if relationships != expected["relationships"]:
            _fail(WITHDRAWAL_POLICY_INVALID, f"{role} relationships differ")
        if subject_types != expected["allowed_subject_types"]:
            _fail(WITHDRAWAL_POLICY_INVALID, f"{role} subject types differ")
        if permission != expected["permission_code"]:
            _fail(WITHDRAWAL_POLICY_INVALID, f"{role} permission differs")
        if maturity != expected["maturity_authority_review"]:
            _fail(WITHDRAWAL_POLICY_INVALID, f"{role} maturity review differs")
        result[role] = AuthorityPolicy(
            relationships=frozenset(relationships),
            permission_code=permission,
            maturity_review=maturity,
            subject_types=frozenset(subject_types),
        )
    return result


def _validate_stores(value: object) -> dict[str, StorePolicy]:
    document = _mapping(
        value,
        code=WITHDRAWAL_POLICY_INVALID,
        location="owner_disposition_matrix",
    )
    _expect_keys(
        document,
        set(EXPECTED_STORES),
        code=WITHDRAWAL_POLICY_INVALID,
        location="owner_disposition_matrix",
    )
    keys = {
        "canonical_owner",
        "data_classification",
        "withdrawal_effect",
        "disposition",
        "activation_dependency",
        "acknowledgement",
        "completion_evidence",
        "legal_hold_behavior",
    }
    result: dict[str, StorePolicy] = {}
    for store_class, expected in EXPECTED_STORES.items():
        item = _mapping(
            document[store_class],
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"owner_disposition_matrix.{store_class}",
        )
        _expect_keys(
            item,
            keys,
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"owner_disposition_matrix.{store_class}",
        )
        actual = tuple(
            _text(
                item[key],
                code=WITHDRAWAL_POLICY_INVALID,
                location=f"owner_disposition_matrix.{store_class}.{key}",
            )
            for key in (
                "canonical_owner",
                "data_classification",
                "withdrawal_effect",
                "disposition",
                "activation_dependency",
                "acknowledgement",
                "completion_evidence",
                "legal_hold_behavior",
            )
        )
        if actual != expected:
            _fail(
                WITHDRAWAL_POLICY_INVALID,
                f"owner_disposition_matrix.{store_class} differs from immutable v1",
            )
        result[store_class] = StorePolicy(
            canonical_owner=actual[0],
            disposition=actual[3],
        )
    return result


def validate_policy(document: dict[str, object]) -> WithdrawalPolicy:
    _expect_keys(
        document,
        {
            "policy_id",
            "version",
            "status",
            "owner",
            "data_classifications",
            "runtime_activation",
            "operations",
            "states",
            "state_transitions",
            "state_precedence",
            "authority_matrix",
            "reason_taxonomy",
            "dispositions",
            "owner_disposition_matrix",
            "legal_hold_and_lawful_basis",
            "orchestration",
            "completion_evidence",
            "audit",
            "stable_reason_codes",
            "public_errors",
            "supersession",
        },
        code=WITHDRAWAL_POLICY_INVALID,
        location="policy",
    )
    if document["policy_id"] != "consent_withdrawal_policy_v1":
        _fail(WITHDRAWAL_POLICY_INVALID, "policy_id must identify immutable v1")
    version = _integer(document["version"], code=WITHDRAWAL_POLICY_INVALID, location="version")
    if version != 1:
        _fail(WITHDRAWAL_POLICY_INVALID, "version must be 1")
    if document["status"] != "approved_for_implementation":
        _fail(WITHDRAWAL_POLICY_INVALID, "status must be approved_for_implementation")
    if document["owner"] != "privacy_consent_owner":
        _fail(WITHDRAWAL_POLICY_INVALID, "owner differs from immutable v1")

    _expect_exact(
        document["data_classifications"],
        {
            "consent_subject_guardian_and_biometric_reference": "Critical",
            "subject_linked_business_evidence_and_propagation_state": ("High_or_Critical"),
            "withdrawal_proof_completion_and_operational_metadata": "High_minimized",
        },
        location="data_classifications",
    )
    _expect_exact(
        document["runtime_activation"],
        {
            "status": "blocked_pending_named_approvals_and_change_record",
            "required_approvals": {
                "privacy_legal": "pending",
                "security_ops": "pending",
                "business_owner": "pending",
                "store_owners": "pending",
            },
            "destructive_execution_requires_separate_change_record": True,
            "missing_or_inactive_policy_behavior": "deny",
            "synthetic_allow_cases_assume_future_named_approvals": True,
        },
        location="runtime_activation",
    )

    operations = _text_set(
        document["operations"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="operations",
    )
    states = _text_set(document["states"], code=WITHDRAWAL_POLICY_INVALID, location="states")
    reasons = _text_set(
        document["reason_taxonomy"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="reason_taxonomy",
    )
    dispositions = _text_set(
        document["dispositions"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="dispositions",
    )
    if operations != EXPECTED_OPERATIONS:
        _fail(WITHDRAWAL_POLICY_INVALID, "operations differ from immutable v1")
    if states != EXPECTED_STATES:
        _fail(WITHDRAWAL_POLICY_INVALID, "states differ from immutable v1")
    if reasons != EXPECTED_REASON_TAXONOMY:
        _fail(WITHDRAWAL_POLICY_INVALID, "reason taxonomy differs from immutable v1")
    if dispositions != EXPECTED_DISPOSITIONS:
        _fail(WITHDRAWAL_POLICY_INVALID, "dispositions differ from immutable v1")

    transitions_document = _mapping(
        document["state_transitions"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="state_transitions",
    )
    _expect_keys(
        transitions_document,
        EXPECTED_STATES,
        code=WITHDRAWAL_POLICY_INVALID,
        location="state_transitions",
    )
    transitions: dict[str, frozenset[str]] = {}
    for state, expected in EXPECTED_TRANSITIONS.items():
        actual = _text_set(
            transitions_document[state],
            code=WITHDRAWAL_POLICY_INVALID,
            location=f"state_transitions.{state}",
        )
        if actual != expected:
            _fail(
                WITHDRAWAL_POLICY_INVALID,
                f"state_transitions.{state} differs from immutable v1",
            )
        transitions[state] = frozenset(actual)

    _expect_exact(
        document["state_precedence"],
        {
            "deny_processing_states": [
                "effective",
                "propagating",
                "partially_completed",
                "completed",
                "superseded",
            ],
            "deny_before_dispose_required": True,
            "effective_denies_new_biometric_processing": True,
            "effective_denies_recognition_and_enrollment": True,
            "effective_denies_subject_linked_notification": True,
            "effective_denies_evidence_access": True,
            "effective_denies_new_report_and_export_use": True,
            "effective_version_remains_deny_after_correction_or_supersession": True,
            "correction_never_overwrites_effective_withdrawal": True,
            "legal_hold_never_changes_withdrawal_state_or_access": True,
            "independent_lawful_basis_never_changes_withdrawal_state_or_access": True,
        },
        location="state_precedence",
    )
    authorities = _validate_authorities(document["authority_matrix"])
    stores = _validate_stores(document["owner_disposition_matrix"])

    _expect_exact(
        document["legal_hold_and_lawful_basis"],
        {
            "legal_hold_required_inputs": [
                "approved_hold_authority",
                "exact_object_scope",
                "exact_purpose",
                "reason_code",
                "effective_at",
                "review_or_expiry_at",
                "approver",
                "audit_reference",
            ],
            "legal_hold_pauses_only_exact_physical_disposition": True,
            "legal_hold_never_grants_consent_processing_access_decrypt_or_export": True,
            "independent_lawful_basis_required_inputs": [
                "basis_code",
                "exact_object_scope",
                "exact_purpose",
                "canonical_owner",
                "active_version",
                "effective_at",
                "review_or_expiry_at",
                "approver",
                "audit_reference",
            ],
            "independent_lawful_basis_retains_only_necessary_restricted_record": True,
            "independent_lawful_basis_never_silently_preserves_every_copy": True,
            "missing_ambiguous_expired_or_broad_scope_behavior": "deny_and_escalate",
        },
        location="legal_hold_and_lawful_basis",
    )
    hold_section = _mapping(
        document["legal_hold_and_lawful_basis"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="legal_hold_and_lawful_basis",
    )
    if (
        _text_set(
            hold_section["legal_hold_required_inputs"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="legal_hold_required_inputs",
        )
        != EXPECTED_HOLD_INPUTS
        or _text_set(
            hold_section["independent_lawful_basis_required_inputs"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="independent_lawful_basis_required_inputs",
        )
        != EXPECTED_BASIS_INPUTS
    ):
        _fail(WITHDRAWAL_POLICY_INVALID, "hold or lawful-basis inputs differ")

    _expect_exact(
        document["orchestration"],
        {
            "canonical_deny_commit_precedes_propagation": True,
            "outbox_after_deny_commit": True,
            "owners_never_delete_another_owner_schema_or_store": True,
            "cross_store_transaction_prohibited": True,
            "owner_acknowledgement_required": True,
            "idempotent_resource_action_required": True,
            "checkpoint_resume_required": True,
            "bounded_retry_and_reconciliation_required": True,
            "partial_failure_state": "partially_completed",
            "partial_failure_never_reenables_processing": True,
            "completion_requires_all_required_owner_acknowledgements": True,
            "restore_must_reapply_effective_withdrawals_before_access": True,
            "stale_restore_blocks_access_until_reconciled": True,
            "metrics": [
                "withdrawal_effective_total",
                "withdrawal_owner_ack_pending",
                "withdrawal_partial_failure_total",
                "withdrawal_reconciliation_lag",
                "withdrawal_restore_reapply_pending",
                "withdrawal_completion_age",
            ],
            "metric_labels_are_low_cardinality_and_redacted": True,
        },
        location="orchestration",
    )
    orchestration = _mapping(
        document["orchestration"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="orchestration",
    )
    if (
        _text_set(
            orchestration["metrics"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="orchestration.metrics",
        )
        != EXPECTED_METRICS
    ):
        _fail(WITHDRAWAL_POLICY_INVALID, "metrics differ from immutable v1")

    completion = _mapping(
        document["completion_evidence"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="completion_evidence",
    )
    _expect_keys(
        completion,
        {
            "required_fields",
            "optional_minimized_fields",
            "forbidden_fields",
            "deleted_content_is_never_copied_into_evidence",
        },
        code=WITHDRAWAL_POLICY_INVALID,
        location="completion_evidence",
    )
    completion_required = _text_set(
        completion["required_fields"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="completion_evidence.required_fields",
    )
    completion_optional = _text_set(
        completion["optional_minimized_fields"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="completion_evidence.optional_minimized_fields",
    )
    completion_forbidden = _text_set(
        completion["forbidden_fields"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="completion_evidence.forbidden_fields",
    )
    if completion_required != EXPECTED_COMPLETION_REQUIRED:
        _fail(WITHDRAWAL_POLICY_INVALID, "completion required fields differ")
    if completion_optional != EXPECTED_COMPLETION_OPTIONAL:
        _fail(WITHDRAWAL_POLICY_INVALID, "completion optional fields differ")
    if completion_forbidden != EXPECTED_FORBIDDEN_FIELDS:
        _fail(WITHDRAWAL_POLICY_INVALID, "completion forbidden fields differ")
    if not _boolean(
        completion["deleted_content_is_never_copied_into_evidence"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="completion_evidence.deleted_content_is_never_copied_into_evidence",
    ):
        _fail(WITHDRAWAL_POLICY_INVALID, "deleted content must never be copied")

    audit = _mapping(document["audit"], code=WITHDRAWAL_POLICY_INVALID, location="audit")
    _expect_keys(
        audit,
        {
            "actions",
            "required_fields",
            "optional_minimized_fields",
            "forbidden_fields",
            "allowed_denied_paused_and_failed_are_append_only",
        },
        code=WITHDRAWAL_POLICY_INVALID,
        location="audit",
    )
    if (
        _text_set(
            audit["actions"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="audit.actions",
        )
        != EXPECTED_AUDIT_ACTIONS
        or _text_set(
            audit["required_fields"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="audit.required_fields",
        )
        != EXPECTED_AUDIT_REQUIRED
        or _text_set(
            audit["optional_minimized_fields"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="audit.optional_minimized_fields",
        )
        != EXPECTED_AUDIT_OPTIONAL
        or _text_set(
            audit["forbidden_fields"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="audit.forbidden_fields",
        )
        != EXPECTED_FORBIDDEN_FIELDS
        or not _boolean(
            audit["allowed_denied_paused_and_failed_are_append_only"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="audit.allowed_denied_paused_and_failed_are_append_only",
        )
    ):
        _fail(WITHDRAWAL_POLICY_INVALID, "audit contract differs from immutable v1")

    reason_codes = _mapping(
        document["stable_reason_codes"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="stable_reason_codes",
    )
    public_errors = _mapping(
        document["public_errors"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="public_errors",
    )
    if reason_codes != EXPECTED_REASON_CODES:
        _fail(WITHDRAWAL_POLICY_INVALID, "stable reason codes differ")
    if public_errors != EXPECTED_PUBLIC_ERRORS:
        _fail(WITHDRAWAL_POLICY_INVALID, "public errors differ")

    supersession = _mapping(
        document["supersession"],
        code=WITHDRAWAL_POLICY_INVALID,
        location="supersession",
    )
    _expect_keys(
        supersession,
        {
            "published_versions_are_immutable",
            "requires_new_version_for",
            "required_evidence",
        },
        code=WITHDRAWAL_POLICY_INVALID,
        location="supersession",
    )
    if (
        not _boolean(
            supersession["published_versions_are_immutable"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="supersession.published_versions_are_immutable",
        )
        or _text_set(
            supersession["requires_new_version_for"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="supersession.requires_new_version_for",
        )
        != EXPECTED_SUPERSESSION_TRIGGERS
        or _text_set(
            supersession["required_evidence"],
            code=WITHDRAWAL_POLICY_INVALID,
            location="supersession.required_evidence",
        )
        != EXPECTED_SUPERSESSION_EVIDENCE
    ):
        _fail(WITHDRAWAL_POLICY_INVALID, "supersession contract differs")

    return WithdrawalPolicy(
        version=version,
        operations=frozenset(operations),
        states=frozenset(states),
        transitions=transitions,
        deny_states=frozenset(EXPECTED_DENY_STATES),
        authorities=authorities,
        stores=stores,
        reasons=frozenset(reasons),
        dispositions=frozenset(dispositions),
        reason_codes=cast(dict[str, str], reason_codes),
        public_errors=cast(dict[str, str], public_errors),
        completion_required=frozenset(completion_required),
        completion_optional=frozenset(completion_optional),
        completion_forbidden=frozenset(completion_forbidden),
    )


def _validate_context(context: dict[str, object]) -> None:
    _expect_keys(
        context,
        CONTEXT_FIELDS,
        code=WITHDRAWAL_FIXTURE_INVALID,
        location="context",
    )
    for field in BOOLEAN_CONTEXT_FIELDS:
        _boolean(
            context[field],
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"context.{field}",
        )
    for field in CONTEXT_FIELDS - BOOLEAN_CONTEXT_FIELDS - {"completion_evidence_fields"}:
        _text(
            context[field],
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"context.{field}",
        )
    _text_set(
        context["completion_evidence_fields"],
        code=WITHDRAWAL_FIXTURE_INVALID,
        location="context.completion_evidence_fields",
    )


def _deny(
    policy: WithdrawalPolicy,
    reason_key: str,
    public_error_key: str,
) -> Decision:
    return Decision(
        decision="deny",
        reason_code=policy.reason_codes[reason_key],
        public_error=policy.public_errors[public_error_key],
    )


def _allow(policy: WithdrawalPolicy, reason_key: str) -> Decision:
    return Decision(
        decision="allow",
        reason_code=policy.reason_codes[reason_key],
        public_error="",
    )


def _transition_allowed(
    policy: WithdrawalPolicy,
    current_state: str,
    transition_to: str,
) -> bool:
    return (
        current_state in policy.transitions and transition_to in policy.transitions[current_state]
    )


def _maturity_authority_allowed(
    authority: AuthorityPolicy,
    subject_type: str,
    status: str,
) -> bool:
    if authority.maturity_review == "not_required":
        return status == "not_required"
    if authority.maturity_review == "decision_must_be_preverified":
        return status == "preverified"
    if authority.maturity_review == "required_for_student" and subject_type == "staff":
        return status == "not_required"
    return status == "resolved_authorized"


def evaluate_withdrawal(
    policy: WithdrawalPolicy,
    context: dict[str, object],
) -> Decision:
    _validate_context(context)
    operation = cast(str, context["operation"])
    if operation not in policy.operations:
        return _deny(policy, "transition_denied", "invalid")
    if context["policy_version_status"] != "active":
        return _deny(policy, "policy_inactive", "invalid")
    if context["runtime_approval_status"] != "approved":
        return _deny(policy, "runtime_approval_missing", "invalid")
    if not context["actor_authenticated"]:
        return _deny(policy, "actor_unauthenticated", "concealed")

    role = cast(str, context["actor_role"])
    authority = policy.authorities.get(role)
    if authority is None:
        return _deny(policy, "actor_authority_denied", "concealed")
    if context["actor_permission_code"] != authority.permission_code:
        return _deny(policy, "actor_authority_denied", "concealed")
    if context["actor_relationship"] not in authority.relationships:
        return _deny(policy, "relationship_denied", "concealed")
    subject_type = cast(str, context["subject_type"])
    if subject_type not in authority.subject_types:
        return _deny(policy, "actor_authority_denied", "concealed")
    if not _maturity_authority_allowed(
        authority,
        subject_type,
        cast(str, context["maturity_authority_status"]),
    ):
        return _deny(policy, "maturity_authority_ambiguous", "concealed")
    if (
        not context["tenant_scope_match"]
        or not context["school_scope_match"]
        or not context["subject_scope_match"]
    ):
        return _deny(policy, "scope_denied", "concealed")
    if context["purpose_status"] != "approved" or context["purpose_code"] != "biometric_processing":
        return _deny(policy, "purpose_denied", "concealed")
    if (
        context["actor_identity_status"] != "verified"
        or context["subject_identity_status"] != "verified"
    ):
        return _deny(policy, "identity_not_verified", "invalid")
    if context["reason_code"] not in policy.reasons:
        return _deny(policy, "reason_denied", "invalid")
    if context["request_version_status"] != "current":
        return _deny(policy, "version_stale", "conflict")
    if context["idempotency_status"] in {"invalid", "duplicate_conflict"}:
        return _deny(policy, "idempotency_denied", "conflict")
    if context["correction_overwrites_effective"]:
        return _deny(policy, "correction_overwrite_denied", "conflict")

    current_state = cast(str, context["current_state"])
    transition_to = cast(str, context["transition_to"])
    if current_state not in policy.states or transition_to not in policy.states:
        return _deny(policy, "transition_denied", "conflict")
    if context["idempotency_status"] == "duplicate_exact":
        if operation == "request":
            return _allow(policy, "duplicate_replayed")
        return _deny(policy, "idempotency_denied", "conflict")

    if operation == "request":
        if current_state != "requested" or transition_to != "requested":
            return _deny(policy, "transition_denied", "conflict")
        return _allow(policy, "request_allowed")
    if operation == "verify_identity":
        if not _transition_allowed(policy, current_state, transition_to) or (
            transition_to != "identity_verified"
        ):
            return _deny(policy, "transition_denied", "conflict")
        return _allow(policy, "identity_verification_allowed")
    if operation == "make_effective":
        if not _transition_allowed(policy, current_state, transition_to) or (
            transition_to != "effective"
        ):
            return _deny(policy, "transition_denied", "conflict")
        if not context["deny_committed_before_disposal"]:
            return _deny(policy, "deny_before_dispose_missing", "conflict")
        return _allow(policy, "effective_allowed")
    if operation == "processing_access":
        if current_state in policy.deny_states:
            return _deny(policy, "processing_denied", "concealed")
        return _deny(
            policy,
            "processing_requires_separate_authorization",
            "concealed",
        )
    if operation == "reject":
        if not _transition_allowed(policy, current_state, transition_to) or (
            transition_to != "rejected"
        ):
            return _deny(policy, "transition_denied", "conflict")
        return _allow(policy, "rejection_allowed")
    if operation == "supersede":
        if not _transition_allowed(policy, current_state, transition_to) or (
            transition_to != "superseded"
        ):
            return _deny(policy, "transition_denied", "conflict")
        if not context["superseding_version_linked"]:
            return _deny(policy, "version_stale", "conflict")
        return _allow(policy, "supersession_allowed")

    if current_state not in policy.deny_states:
        return _deny(policy, "transition_denied", "conflict")
    if not context["deny_committed_before_disposal"]:
        return _deny(policy, "deny_before_dispose_missing", "conflict")

    store_class = cast(str, context["store_class"])
    store = policy.stores.get(store_class)
    if store is None or context["canonical_owner"] != store.canonical_owner:
        return _deny(policy, "owner_scope_denied", "concealed")
    disposition = cast(str, context["disposition"])
    if disposition not in policy.dispositions:
        return _deny(policy, "disposition_denied", "conflict")

    if context["lawful_basis_active"]:
        if (
            context["lawful_basis_scope_status"] != "exact"
            or context["lawful_basis_purpose_status"] != "exact"
            or context["lawful_basis_owner_status"] != "approved"
            or context["lawful_basis_version_status"] != "active"
        ):
            return _deny(policy, "lawful_basis_scope_invalid", "conflict")
        if disposition != "retain_restricted_proof" or not context["restricted_retention_applied"]:
            return _deny(policy, "restricted_retention_required", "conflict")
    elif disposition != store.disposition:
        return _deny(policy, "disposition_denied", "conflict")

    if context["activation_dependency_status"] != "approved":
        return _deny(policy, "activation_dependency_missing", "conflict")
    if not context["dependency_available"]:
        return _deny(policy, "dependency_unavailable", "dependency_unavailable")
    destructive_dispositions = {
        "unlink_identity",
        "delete_exact_media_or_reference",
        "anonymize_approved_fields",
    }
    if disposition in destructive_dispositions and not context["destructive_execution_requested"]:
        return _deny(policy, "change_record_required", "conflict")
    if context["physical_disposition_requested"] and not context["destructive_execution_requested"]:
        return _deny(policy, "change_record_required", "conflict")
    if (
        context["destructive_execution_requested"]
        and context["destructive_change_record_status"] != "authorized"
    ):
        return _deny(policy, "change_record_required", "conflict")

    if context["legal_hold_active"]:
        if (
            context["legal_hold_scope_status"] != "exact"
            or context["legal_hold_authority_status"] != "approved"
        ):
            return _deny(policy, "legal_hold_scope_invalid", "conflict")
        if context["physical_disposition_requested"]:
            return _deny(policy, "disposition_paused_legal_hold", "pending")

    if context["checkpoint_status"] != "valid":
        return _deny(policy, "checkpoint_invalid", "conflict")
    if context["reconciliation_status"] != "bounded":
        return _deny(policy, "reconciliation_unbounded", "conflict")
    if context["restore_reapply_pending"] and operation != "reconcile":
        return _deny(policy, "restore_reapply_pending", "pending")
    if (
        context["restore_reapply_pending"]
        and operation == "reconcile"
        and not context["restore_reapply_authorized"]
    ):
        return _deny(policy, "restore_reapply_pending", "pending")

    if operation == "acknowledge":
        if current_state not in {
            "effective",
            "propagating",
            "partially_completed",
        }:
            return _deny(policy, "transition_denied", "conflict")
        if context["owner_acknowledgement_status"] != "acknowledged":
            return _deny(policy, "owner_acknowledgement_missing", "pending")
        return _allow(policy, "acknowledgement_allowed")
    if operation == "propagate":
        if transition_to not in {"propagating", "partially_completed"}:
            return _deny(policy, "transition_denied", "conflict")
        if transition_to != current_state and not _transition_allowed(
            policy, current_state, transition_to
        ):
            return _deny(policy, "transition_denied", "conflict")
        return _allow(policy, "propagation_allowed")
    if operation == "reconcile":
        if current_state not in {"propagating", "partially_completed"}:
            return _deny(policy, "transition_denied", "conflict")
        if transition_to != "propagating":
            return _deny(policy, "transition_denied", "conflict")
        if transition_to != current_state and not _transition_allowed(
            policy, current_state, transition_to
        ):
            return _deny(policy, "transition_denied", "conflict")
        return _allow(policy, "reconciliation_allowed")
    if operation == "complete":
        if (
            current_state not in {"effective", "propagating", "partially_completed"}
            or transition_to != "completed"
            or not _transition_allowed(policy, current_state, transition_to)
        ):
            return _deny(policy, "transition_denied", "conflict")
        if context["partial_failure_open"]:
            return _deny(policy, "partial_failure_open", "pending")
        if not context["all_required_owner_acknowledged"]:
            return _deny(policy, "owner_acknowledgement_missing", "pending")
        evidence_fields = _text_set(
            context["completion_evidence_fields"],
            code=WITHDRAWAL_FIXTURE_INVALID,
            location="context.completion_evidence_fields",
        )
        allowed_fields = policy.completion_required | policy.completion_optional
        if (
            not policy.completion_required.issubset(evidence_fields)
            or not evidence_fields.issubset(allowed_fields)
            or evidence_fields & policy.completion_forbidden
        ):
            return _deny(policy, "completion_evidence_invalid", "invalid")
        return _allow(policy, "completion_allowed")

    return _deny(policy, "transition_denied", "invalid")


def validate_fixture(
    document: dict[str, object],
    policy: WithdrawalPolicy,
) -> int:
    _expect_keys(
        document,
        {
            "_fixture",
            "fixture_id",
            "synthetic_only",
            "contains_real_personal_data",
            "contains_real_biometric_or_media",
            "contains_real_database_or_provider_data",
            "default_context",
            "cases",
        },
        code=WITHDRAWAL_FIXTURE_INVALID,
        location="fixture",
    )
    if document["_fixture"] != "SYNTHETIC_TEST_DATA_ONLY":
        _fail(WITHDRAWAL_FIXTURE_INVALID, "synthetic marker is missing")
    if document["fixture_id"] != "test_consent_withdrawal_policy_v1_cases":
        _fail(WITHDRAWAL_FIXTURE_INVALID, "fixture_id differs from synthetic v1")
    if document["synthetic_only"] is not True:
        _fail(WITHDRAWAL_FIXTURE_INVALID, "fixture must be synthetic only")
    if (
        document["contains_real_personal_data"] is not False
        or document["contains_real_biometric_or_media"] is not False
        or document["contains_real_database_or_provider_data"] is not False
    ):
        _fail(WITHDRAWAL_FIXTURE_INVALID, "fixture declares unsafe data")

    default_context = _mapping(
        document["default_context"],
        code=WITHDRAWAL_FIXTURE_INVALID,
        location="default_context",
    )
    _validate_context(default_context)
    raw_cases = document["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        _fail(WITHDRAWAL_FIXTURE_INVALID, "cases must be a non-empty list")

    seen: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        case = _mapping(
            raw_case,
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"cases[{index}]",
        )
        _expect_keys(
            case,
            {
                "case_code",
                "overrides",
                "expected_decision",
                "expected_reason_code",
                "expected_public_error",
            },
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"cases[{index}]",
        )
        case_code = _text(
            case["case_code"],
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"cases[{index}].case_code",
        )
        if not CASE_CODE.fullmatch(case_code) or case_code in seen:
            _fail(WITHDRAWAL_FIXTURE_INVALID, "case_code is invalid or duplicated")
        seen.add(case_code)
        overrides = _mapping(
            case["overrides"],
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"cases[{index}].overrides",
        )
        unknown = set(overrides) - CONTEXT_FIELDS
        if unknown:
            _fail(
                WITHDRAWAL_FIXTURE_INVALID,
                f"case {case_code} has unknown overrides {sorted(unknown)}",
            )
        context = dict(default_context)
        context.update(overrides)
        decision = evaluate_withdrawal(policy, context)
        expected_decision = _text(
            case["expected_decision"],
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"cases[{index}].expected_decision",
        )
        expected_reason = _text(
            case["expected_reason_code"],
            code=WITHDRAWAL_FIXTURE_INVALID,
            location=f"cases[{index}].expected_reason_code",
        )
        expected_public_error = case["expected_public_error"]
        if not isinstance(expected_public_error, str):
            _fail(
                WITHDRAWAL_FIXTURE_INVALID,
                f"cases[{index}].expected_public_error must be text",
            )
        if (
            decision.decision != expected_decision
            or decision.reason_code != expected_reason
            or decision.public_error != expected_public_error
        ):
            _fail(
                WITHDRAWAL_FIXTURE_INVALID,
                f"case {case_code} outcome differs from expected compatibility record",
            )
    return len(raw_cases)


def _load_document(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WithdrawalPolicyError(f"cannot load {path}") from exc
    return _mapping(value, code=WITHDRAWAL_POLICY_INVALID, location=str(path))


def main() -> int:
    try:
        policy_document = _load_document(REPO_ROOT / POLICY_PATH)
        policy = validate_policy(policy_document)
        fixture_document = _load_document(REPO_ROOT / FIXTURE_PATH)
        case_count = validate_fixture(fixture_document, policy)
    except WithdrawalPolicyError:
        print("consent_withdrawal_policy=FAIL")
        return 1
    print("consent_withdrawal_policy=PASS")
    print("policy_version=consent_withdrawal_policy_v1")
    print("runtime_activation=BLOCKED_PENDING_NAMED_APPROVALS_AND_CHANGE_RECORD")
    print(f"synthetic_cases_checked={case_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
