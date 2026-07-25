"""Validate the versioned evidence-access policy and synthetic decision matrix."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Never

POLICY_PATH = Path("packages/evidence-access-policy/evidence-access-policy-v1.json")
FIXTURE_PATH = Path(
    "packages/test-fixtures/evidence-access/evidence-access-policy-cases.synthetic.json"
)
SYNTHETIC_MARKER = "SYNTHETIC_TEST_DATA_ONLY"

EVIDENCE_POLICY_INVALID = "EVIDENCE_POLICY_INVALID"
CASE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")
PERMISSION_CODE = re.compile(r"^(?:evidence|service)\.[a-z][a-z0-9_.]{2,95}$")
STABLE_CODE = re.compile(r"^EVIDENCE_[A-Z0-9_]{2,95}$")

ACTION_EXPECTATIONS: dict[str, tuple[str, str, str | None, bool, bool, bool]] = {
    "view_metadata": (
        "evidence.view_metadata",
        "metadata_only",
        None,
        False,
        False,
        False,
    ),
    "view_thumbnail": (
        "evidence.view_thumbnail",
        "inline_thumbnail",
        "standard_view",
        False,
        False,
        False,
    ),
    "view_original": (
        "evidence.view_original",
        "inline_original",
        "standard_view",
        True,
        False,
        False,
    ),
    "download": (
        "evidence.download",
        "attachment",
        "standard_view",
        True,
        False,
        False,
    ),
    "export": (
        "evidence.export",
        "export_artifact",
        "export_delivery",
        True,
        True,
        True,
    ),
}

ROLE_EXPECTATIONS: dict[str, tuple[str, frozenset[str], frozenset[str], bool, str | None]] = {
    "subject_self": (
        "human",
        frozenset({"view_metadata", "view_thumbnail"}),
        frozenset({"own_staff_record"}),
        False,
        None,
    ),
    "parent_guardian": (
        "human",
        frozenset({"view_metadata", "view_thumbnail"}),
        frozenset({"linked_child"}),
        False,
        None,
    ),
    "teacher_subject": (
        "human",
        frozenset({"view_metadata", "view_thumbnail"}),
        frozenset({"assigned_class_schedule_task"}),
        False,
        None,
    ),
    "teacher_homeroom": (
        "human",
        frozenset({"view_metadata", "view_thumbnail"}),
        frozenset({"assigned_homeroom"}),
        False,
        None,
    ),
    "hr_officer": (
        "human",
        frozenset(ACTION_EXPECTATIONS),
        frozenset({"assigned_hr_unit"}),
        False,
        None,
    ),
    "bgh": (
        "human",
        frozenset(ACTION_EXPECTATIONS),
        frozenset({"assigned_school"}),
        False,
        None,
    ),
    "kitchen_manager": (
        "human",
        frozenset({"view_metadata", "view_thumbnail", "view_original"}),
        frozenset({"assigned_kitchen_zone_shift"}),
        False,
        None,
    ),
    "security_reviewer": (
        "human",
        frozenset(ACTION_EXPECTATIONS),
        frozenset({"assigned_zone_camera"}),
        False,
        None,
    ),
    "privacy_officer": (
        "human",
        frozenset({"view_metadata"}),
        frozenset({"approved_privacy_ticket"}),
        False,
        None,
    ),
    "auditor": (
        "human",
        frozenset({"view_metadata"}),
        frozenset({"approved_audit_ticket"}),
        False,
        None,
    ),
    "school_admin": ("human", frozenset(), frozenset(), False, None),
    "system_admin": ("human", frozenset(), frozenset(), False, None),
    "technical_operator": ("human", frozenset(), frozenset(), False, None),
    "evidence_service": (
        "service",
        frozenset(ACTION_EXPECTATIONS),
        frozenset({"delegated_authorized_scope"}),
        True,
        "service.evidence.deliver",
    ),
    "report_service": (
        "service",
        frozenset({"export"}),
        frozenset({"approved_export_scope"}),
        True,
        "service.report.export",
    ),
    "notification_service": (
        "service",
        frozenset(),
        frozenset(),
        False,
        "service.notification.reference_only",
    ),
}

EXPECTED_AUTHORIZATION_INPUTS = [
    "authenticated_actor",
    "trusted_service_identity_for_service_actor",
    "tenant_scope",
    "school_scope",
    "object_scope",
    "relationship_or_assignment",
    "requested_action",
    "explicit_permission",
    "approved_purpose",
    "consent_snapshot_when_applicable",
    "evidence_sensitivity",
    "evidence_state",
    "retention_state",
    "legal_hold_state",
    "policy_version",
    "reason_code_when_required",
    "request_and_correlation_id",
    "delegation_context_for_service_actor",
]

EXPECTED_REASON_CODES = {
    "access_allowed": "EVIDENCE_ACCESS_ALLOWED",
    "actor_unauthenticated": "EVIDENCE_ACTOR_UNAUTHENTICATED",
    "service_identity_denied": "EVIDENCE_SERVICE_IDENTITY_DENIED",
    "delegation_required": "EVIDENCE_DELEGATION_REQUIRED",
    "tenant_scope_denied": "EVIDENCE_TENANT_SCOPE_DENIED",
    "school_scope_denied": "EVIDENCE_SCHOOL_SCOPE_DENIED",
    "object_scope_denied": "EVIDENCE_OBJECT_SCOPE_DENIED",
    "action_denied": "EVIDENCE_ACTION_DENIED",
    "permission_denied": "EVIDENCE_PERMISSION_DENIED",
    "purpose_required": "EVIDENCE_PURPOSE_REQUIRED",
    "purpose_denied": "EVIDENCE_PURPOSE_DENIED",
    "consent_required": "EVIDENCE_CONSENT_REQUIRED",
    "consent_denied": "EVIDENCE_CONSENT_DENIED",
    "not_found": "EVIDENCE_NOT_FOUND",
    "upload_pending": "EVIDENCE_UPLOAD_PENDING",
    "quarantined": "EVIDENCE_QUARANTINED",
    "not_available": "EVIDENCE_NOT_AVAILABLE",
    "deleted": "EVIDENCE_DELETED",
    "retention_expired": "EVIDENCE_RETENTION_EXPIRED",
    "legal_hold_unresolved": "EVIDENCE_LEGAL_HOLD_UNRESOLVED",
    "ttl_invalid": "EVIDENCE_URL_TTL_INVALID",
    "reason_required": "EVIDENCE_REASON_REQUIRED",
    "reason_invalid": "EVIDENCE_REASON_INVALID",
    "export_approval_required": "EVIDENCE_EXPORT_APPROVAL_REQUIRED",
    "export_recipient_invalid": "EVIDENCE_EXPORT_RECIPIENT_INVALID",
    "export_artifact_ttl_invalid": "EVIDENCE_EXPORT_ARTIFACT_TTL_INVALID",
    "authorization_dependency_unavailable": "EVIDENCE_AUTHZ_DEPENDENCY_UNAVAILABLE",
}

EXPECTED_AUDIT_FIELDS = frozenset(
    {
        "audit_event_id",
        "occurred_at",
        "actor_id",
        "actor_type",
        "tenant_id",
        "school_id",
        "evidence_object_id",
        "resource_type",
        "resource_id",
        "requested_action",
        "purpose_code",
        "policy_version",
        "outcome",
        "reason_code",
        "request_id",
        "correlation_id",
        "url_ttl_seconds",
        "export_request_id",
        "recipient_control_code",
    }
)

EXPECTED_AUDIT_FORBIDDEN_FIELDS = frozenset(
    {
        "signed_url",
        "object_key",
        "bucket_name",
        "provider_version_id",
        "media_binary",
        "image_base64",
        "video_base64",
        "face_embedding",
        "biometric_payload",
        "raw_ansvis_payload",
        "access_token",
        "refresh_token",
        "credential",
        "personal_profile",
        "free_form_note",
    }
)

CONTEXT_FIELDS = frozenset(
    {
        "actor_authenticated",
        "actor_kind",
        "actor_role",
        "trusted_service_identity",
        "service_permission_granted",
        "service_permission_code",
        "delegation_status",
        "requested_action",
        "permission_code",
        "tenant_scope_match",
        "school_scope_match",
        "object_scope_match",
        "relationship_scope",
        "purpose_status",
        "consent_requirement",
        "consent_status",
        "evidence_sensitivity",
        "resource_exists",
        "evidence_state",
        "retention_status",
        "legal_hold_status",
        "authorization_dependencies_available",
        "reason_code",
        "url_ttl_seconds",
        "export_approval_status",
        "export_recipient_status",
        "export_artifact_ttl_seconds",
    }
)


class EvidencePolicyError(ValueError):
    """Fail closed without returning rejected fixture or protected context."""

    def __init__(self, code: str = EVIDENCE_POLICY_INVALID) -> None:
        self.code = code
        super().__init__(code)


def _fail() -> Never:
    raise EvidencePolicyError()


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail()
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        _fail()
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        _fail()
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        _fail()
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail()
    return value


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    return _integer(value)


def _text_set(value: object) -> frozenset[str]:
    items = [_text(item) for item in _list(value)]
    if len(items) != len(set(items)):
        _fail()
    return frozenset(items)


def _load_json(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _fail()
    return _mapping(value)


@dataclass(frozen=True, slots=True)
class SignedGetProfile:
    default_ttl_seconds: int
    minimum_ttl_seconds: int
    hard_max_ttl_seconds: int


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    permission_code: str
    signed_get_profile: str | None
    reason_code_required: bool
    export_approval_required: bool
    recipient_control_required: bool


@dataclass(frozen=True, slots=True)
class RolePolicy:
    actor_kind: str
    candidate_actions: frozenset[str]
    allowed_relationship_scopes: frozenset[str]
    delegation_required: bool
    service_permission_code: str | None


@dataclass(frozen=True, slots=True)
class EvidenceAccessPolicy:
    policy_version: str
    actions: dict[str, ActionPolicy]
    roles: dict[str, RolePolicy]
    signed_get_profiles: dict[str, SignedGetProfile]
    readable_states: frozenset[str]
    recognized_states: frozenset[str]
    recognized_consent_statuses: frozenset[str]
    recognized_legal_hold_statuses: frozenset[str]
    export_artifact_hard_max_ttl_seconds: int
    access_reason_codes: frozenset[str]
    export_reason_codes: frozenset[str]
    export_recipient_controls: frozenset[str]
    reason_codes: dict[str, str]
    public_errors: dict[str, str]


@dataclass(frozen=True, slots=True)
class AccessDecision:
    decision: str
    reason_code: str
    public_error: str
    ttl_seconds: int | None


def _validate_actions(value: object) -> dict[str, ActionPolicy]:
    document = _mapping(value)
    if set(document) != set(ACTION_EXPECTATIONS):
        _fail()
    result: dict[str, ActionPolicy] = {}
    fields = {
        "permission_code",
        "delivery_kind",
        "signed_get_profile",
        "reason_code_required",
        "export_approval_required",
        "recipient_control_required",
    }
    for name, expected in ACTION_EXPECTATIONS.items():
        item = _mapping(document[name])
        if set(item) != fields:
            _fail()
        permission = _text(item["permission_code"])
        signed_profile_value = item["signed_get_profile"]
        signed_profile = None if signed_profile_value is None else _text(signed_profile_value)
        actual = (
            permission,
            _text(item["delivery_kind"]),
            signed_profile,
            _boolean(item["reason_code_required"]),
            _boolean(item["export_approval_required"]),
            _boolean(item["recipient_control_required"]),
        )
        if actual != expected or PERMISSION_CODE.fullmatch(permission) is None:
            _fail()
        result[name] = ActionPolicy(
            permission_code=permission,
            signed_get_profile=signed_profile,
            reason_code_required=actual[3],
            export_approval_required=actual[4],
            recipient_control_required=actual[5],
        )
    return result


def _validate_roles(value: object) -> dict[str, RolePolicy]:
    document = _mapping(value)
    if set(document) != set(ROLE_EXPECTATIONS):
        _fail()
    result: dict[str, RolePolicy] = {}
    fields = {
        "actor_kind",
        "candidate_actions",
        "allowed_relationship_scopes",
        "delegation_required",
        "service_permission_code",
    }
    for name, expected in ROLE_EXPECTATIONS.items():
        item = _mapping(document[name])
        if set(item) != fields:
            _fail()
        service_permission_value = item["service_permission_code"]
        service_permission = (
            None if service_permission_value is None else _text(service_permission_value)
        )
        actual = (
            _text(item["actor_kind"]),
            _text_set(item["candidate_actions"]),
            _text_set(item["allowed_relationship_scopes"]),
            _boolean(item["delegation_required"]),
            service_permission,
        )
        if actual != expected:
            _fail()
        if service_permission is not None and PERMISSION_CODE.fullmatch(service_permission) is None:
            _fail()
        result[name] = RolePolicy(
            actor_kind=actual[0],
            candidate_actions=actual[1],
            allowed_relationship_scopes=actual[2],
            delegation_required=actual[3],
            service_permission_code=actual[4],
        )
    return result


def _validate_signed_get(value: object) -> dict[str, SignedGetProfile]:
    document = _mapping(value)
    if set(document) != {
        "profiles",
        "method",
        "persistence_allowed",
        "logging_allowed",
        "notification_delivery_allowed",
        "client_storage_allowed",
        "response_headers",
    }:
        _fail()
    if (
        document["method"] != "GET"
        or document["persistence_allowed"] is not False
        or document["logging_allowed"] is not False
        or document["notification_delivery_allowed"] is not False
        or document["client_storage_allowed"] is not False
        or _mapping(document["response_headers"])
        != {
            "cache_control": "private, no-store",
            "x_content_type_options": "nosniff",
            "content_disposition": "safe_allowlisted",
        }
    ):
        _fail()
    profiles = _mapping(document["profiles"])
    expected_profiles = {
        "standard_view": (60, 1, 300),
        "export_delivery": (60, 1, 120),
    }
    if set(profiles) != set(expected_profiles):
        _fail()
    result: dict[str, SignedGetProfile] = {}
    for name, expected in expected_profiles.items():
        profile = _mapping(profiles[name])
        if set(profile) != {
            "default_ttl_seconds",
            "minimum_ttl_seconds",
            "hard_max_ttl_seconds",
        }:
            _fail()
        actual = (
            _integer(profile["default_ttl_seconds"]),
            _integer(profile["minimum_ttl_seconds"]),
            _integer(profile["hard_max_ttl_seconds"]),
        )
        if actual != expected:
            _fail()
        result[name] = SignedGetProfile(*actual)
    return result


def validate_policy(document: dict[str, object]) -> EvidenceAccessPolicy:
    expected_top_level = {
        "policy_id",
        "policy_version",
        "status",
        "runtime_activation",
        "owner_code",
        "technical_review",
        "data_classes",
        "default_decision",
        "public_existence_concealment",
        "authorization_inputs",
        "actions",
        "access_reason_code_allowlist",
        "role_matrix",
        "evidence_states",
        "retention",
        "consent",
        "legal_hold",
        "signed_get",
        "export",
        "audit",
        "stable_reason_codes",
        "public_errors",
        "supersession",
    }
    if set(document) != expected_top_level:
        _fail()
    fixed_values = {
        "policy_id": "evidence_access",
        "policy_version": "evidence_access_policy_v1",
        "status": "approved_for_implementation",
        "owner_code": "evidence_service_security_owner",
        "default_decision": "deny",
        "public_existence_concealment": True,
    }
    if any(document.get(key) != value for key, value in fixed_values.items()):
        _fail()
    if _mapping(document["runtime_activation"]) != {
        "status": "blocked_pending_named_approvals",
        "implementation_authority": "issue_31",
        "required_approvals": {
            "privacy_legal": "pending",
            "security_ops": "pending",
            "business_owner": "pending",
        },
    }:
        _fail()
    if _mapping(document["technical_review"]) != {
        "status": "single_developer_self_reviewed",
        "evidence_code": "issue_31_verification",
    }:
        _fail()
    if _list(document["data_classes"]) != ["high", "critical"]:
        _fail()
    if _list(document["authorization_inputs"]) != EXPECTED_AUTHORIZATION_INPUTS:
        _fail()

    actions = _validate_actions(document["actions"])
    access_reason_codes = _text_set(document["access_reason_code_allowlist"])
    if access_reason_codes != frozenset(
        {
            "BUSINESS_REVIEW",
            "ATTENDANCE_AUDIT",
            "TIMEKEEPING_AUDIT",
            "VIOLATION_REVIEW",
            "SECURITY_INVESTIGATION",
            "LEGAL_REQUEST",
            "DATA_SUBJECT_REQUEST",
            "MANAGEMENT_REPORT",
        }
    ):
        _fail()
    roles = _validate_roles(document["role_matrix"])
    signed_get_profiles = _validate_signed_get(document["signed_get"])

    evidence_states = _mapping(document["evidence_states"])
    if set(evidence_states) != {"recognized", "readable"}:
        _fail()
    recognized_states = _text_set(evidence_states["recognized"])
    readable_states = _text_set(evidence_states["readable"])
    if recognized_states != frozenset(
        {"pending_upload", "quarantined", "available", "delete_pending", "deleted", "missing"}
    ) or readable_states != frozenset({"available"}):
        _fail()

    if _mapping(document["retention"]) != {
        "required_status": "active",
        "expired_denied_before_physical_disposal": True,
        "source_hold_does_not_extend_export_artifact": True,
    }:
        _fail()

    consent = _mapping(document["consent"])
    if set(consent) != {
        "recognized_statuses",
        "required_result",
        "missing_or_ambiguous_decision",
    }:
        _fail()
    recognized_consent = _text_set(consent["recognized_statuses"])
    if (
        recognized_consent != frozenset({"allowed", "blocked", "not_required"})
        or consent["required_result"] != "allowed"
        or consent["missing_or_ambiguous_decision"] != "deny"
    ):
        _fail()

    hold = _mapping(document["legal_hold"])
    if set(hold) != {
        "recognized_statuses",
        "active_blocks_disposal_only",
        "active_does_not_grant_access",
        "active_does_not_extend_expired_access",
        "missing_or_ambiguous_decision",
    }:
        _fail()
    recognized_hold = _text_set(hold["recognized_statuses"])
    if (
        recognized_hold != frozenset({"none", "active", "released"})
        or hold["active_blocks_disposal_only"] is not True
        or hold["active_does_not_grant_access"] is not True
        or hold["active_does_not_extend_expired_access"] is not True
        or hold["missing_or_ambiguous_decision"] != "deny"
    ):
        _fail()

    export = _mapping(document["export"])
    if set(export) != {
        "artifact_default_ttl_seconds",
        "artifact_hard_max_ttl_seconds",
        "source_authorization_required_at_request",
        "source_authorization_required_at_delivery",
        "ordinary_view_or_download_does_not_imply_export",
        "distinct_artifact_hold_required",
        "reason_code_allowlist",
        "recipient_control_allowlist",
    }:
        _fail()
    if (
        export["artifact_default_ttl_seconds"] != 604800
        or export["artifact_hard_max_ttl_seconds"] != 604800
        or export["source_authorization_required_at_request"] is not True
        or export["source_authorization_required_at_delivery"] is not True
        or export["ordinary_view_or_download_does_not_imply_export"] is not True
        or export["distinct_artifact_hold_required"] is not True
    ):
        _fail()
    reason_allowlist = _text_set(export["reason_code_allowlist"])
    if reason_allowlist != frozenset(
        {
            "ATTENDANCE_AUDIT",
            "TIMEKEEPING_AUDIT",
            "VIOLATION_REVIEW",
            "SECURITY_INVESTIGATION",
            "LEGAL_REQUEST",
            "DATA_SUBJECT_REQUEST",
            "MANAGEMENT_REPORT",
        }
    ):
        _fail()
    recipient_controls = _text_set(export["recipient_control_allowlist"])
    if recipient_controls != frozenset(
        {
            "authenticated_requester",
            "approved_internal_recipient",
            "approved_external_recipient_with_expiry",
        }
    ):
        _fail()

    audit = _mapping(document["audit"])
    if set(audit) != {"outcomes", "required_fields", "forbidden_fields", "event_codes"}:
        _fail()
    audit_fields = _text_set(audit["required_fields"])
    forbidden_fields = _text_set(audit["forbidden_fields"])
    if (
        _list(audit["outcomes"]) != ["allowed", "denied"]
        or audit_fields != EXPECTED_AUDIT_FIELDS
        or forbidden_fields != EXPECTED_AUDIT_FORBIDDEN_FIELDS
        or audit_fields & forbidden_fields
        or _mapping(audit["event_codes"])
        != {
            "view_allowed": "EVIDENCE_VIEW_GRANTED",
            "view_denied": "EVIDENCE_VIEW_DENIED",
            "download_allowed": "EVIDENCE_DOWNLOAD_GRANTED",
            "download_denied": "EVIDENCE_DOWNLOAD_DENIED",
            "export_allowed": "EVIDENCE_EXPORT_GRANTED",
            "export_denied": "EVIDENCE_EXPORT_DENIED",
            "export_delivered": "EVIDENCE_EXPORT_DELIVERED",
            "export_expired": "EVIDENCE_EXPORT_EXPIRED",
        }
    ):
        _fail()

    reason_codes_document = _mapping(document["stable_reason_codes"])
    reason_codes = {key: _text(value) for key, value in reason_codes_document.items()}
    if (
        reason_codes != EXPECTED_REASON_CODES
        or len(reason_codes.values()) != len(set(reason_codes.values()))
        or any(STABLE_CODE.fullmatch(code) is None for code in reason_codes.values())
    ):
        _fail()

    public_errors_document = _mapping(document["public_errors"])
    expected_public_errors: dict[str, object] = {
        "resource_concealed": "EVIDENCE_NOT_FOUND",
        "not_available": "EVIDENCE_NOT_AVAILABLE",
        "invalid_request": "EVIDENCE_ACCESS_INVALID",
        "dependency_unavailable": "EVIDENCE_ACCESS_UNAVAILABLE",
        "url_issue_failed": "EVIDENCE_URL_ISSUE_FAILED",
        "unauthorized_and_missing_same_response": True,
        "error_shape": ["error_code", "message", "request_id"],
    }
    if public_errors_document != expected_public_errors:
        _fail()
    public_errors = {
        key: _text(public_errors_document[key])
        for key in (
            "resource_concealed",
            "not_available",
            "invalid_request",
            "dependency_unavailable",
            "url_issue_failed",
        )
    }

    supersession = _mapping(document["supersession"])
    if (
        supersession.get("published_version_immutable") is not True
        or supersession.get("replacement_status") != "retired"
        or _text_set(supersession.get("review_triggers"))
        != frozenset(
            {
                "role_or_permission_change",
                "consent_or_retention_change",
                "new_evidence_type_or_sensitivity",
                "storage_or_delivery_provider_change",
                "security_incident_or_audit_finding",
                "legal_or_customer_policy_change",
                "ttl_or_export_behavior_change",
            }
        )
    ):
        _fail()

    return EvidenceAccessPolicy(
        policy_version=_text(document["policy_version"]),
        actions=actions,
        roles=roles,
        signed_get_profiles=signed_get_profiles,
        readable_states=readable_states,
        recognized_states=recognized_states,
        recognized_consent_statuses=recognized_consent,
        recognized_legal_hold_statuses=recognized_hold,
        export_artifact_hard_max_ttl_seconds=_integer(export["artifact_hard_max_ttl_seconds"]),
        access_reason_codes=access_reason_codes,
        export_reason_codes=reason_allowlist,
        export_recipient_controls=recipient_controls,
        reason_codes=reason_codes,
        public_errors=public_errors,
    )


def _public_error(policy: EvidenceAccessPolicy, reason_key: str) -> str:
    concealed = {
        "actor_unauthenticated",
        "service_identity_denied",
        "delegation_required",
        "tenant_scope_denied",
        "school_scope_denied",
        "object_scope_denied",
        "action_denied",
        "permission_denied",
        "not_found",
    }
    unavailable = {
        "purpose_required",
        "purpose_denied",
        "consent_required",
        "consent_denied",
        "upload_pending",
        "quarantined",
        "not_available",
        "deleted",
        "retention_expired",
        "legal_hold_unresolved",
    }
    invalid = {
        "ttl_invalid",
        "reason_required",
        "reason_invalid",
        "export_approval_required",
        "export_recipient_invalid",
        "export_artifact_ttl_invalid",
    }
    if reason_key in concealed:
        return policy.public_errors["resource_concealed"]
    if reason_key in unavailable:
        return policy.public_errors["not_available"]
    if reason_key in invalid:
        return policy.public_errors["invalid_request"]
    if reason_key == "authorization_dependency_unavailable":
        return policy.public_errors["dependency_unavailable"]
    _fail()


def _deny(policy: EvidenceAccessPolicy, reason_key: str) -> AccessDecision:
    return AccessDecision(
        decision="deny",
        reason_code=policy.reason_codes[reason_key],
        public_error=_public_error(policy, reason_key),
        ttl_seconds=None,
    )


def _signed_ttl(
    context: dict[str, object],
    policy: EvidenceAccessPolicy,
    action: ActionPolicy,
) -> int | None:
    if action.signed_get_profile is None:
        if context["url_ttl_seconds"] is not None:
            raise EvidencePolicyError(policy.reason_codes["ttl_invalid"])
        return None
    profile = policy.signed_get_profiles[action.signed_get_profile]
    requested = _optional_integer(context["url_ttl_seconds"])
    ttl = profile.default_ttl_seconds if requested is None else requested
    if ttl < profile.minimum_ttl_seconds or ttl > profile.hard_max_ttl_seconds:
        raise EvidencePolicyError(policy.reason_codes["ttl_invalid"])
    return ttl


def evaluate_access(
    context: dict[str, object],
    policy: EvidenceAccessPolicy,
) -> AccessDecision:
    if set(context) != CONTEXT_FIELDS:
        _fail()
    if not _boolean(context["authorization_dependencies_available"]):
        return _deny(policy, "authorization_dependency_unavailable")
    if not _boolean(context["actor_authenticated"]):
        return _deny(policy, "actor_unauthenticated")

    actor_role = _text(context["actor_role"])
    role = policy.roles.get(actor_role)
    actor_kind = _text(context["actor_kind"])
    if role is None or actor_kind != role.actor_kind:
        return _deny(policy, "action_denied")
    if actor_kind == "service":
        if not _boolean(context["trusted_service_identity"]):
            return _deny(policy, "service_identity_denied")
        if (
            role.service_permission_code is None
            or not _boolean(context["service_permission_granted"])
            or context["service_permission_code"] != role.service_permission_code
        ):
            return _deny(policy, "service_identity_denied")
        if role.delegation_required and context["delegation_status"] != "approved":
            return _deny(policy, "delegation_required")

    if not _boolean(context["resource_exists"]):
        return _deny(policy, "not_found")
    if not _boolean(context["tenant_scope_match"]):
        return _deny(policy, "tenant_scope_denied")
    if not _boolean(context["school_scope_match"]):
        return _deny(policy, "school_scope_denied")
    if not _boolean(context["object_scope_match"]):
        return _deny(policy, "object_scope_denied")

    requested_action = _text(context["requested_action"])
    action = policy.actions.get(requested_action)
    if action is None or requested_action not in role.candidate_actions:
        return _deny(policy, "action_denied")
    if _text(context["relationship_scope"]) not in role.allowed_relationship_scopes:
        return _deny(policy, "object_scope_denied")
    if context["permission_code"] != action.permission_code:
        return _deny(policy, "permission_denied")

    purpose = _text(context["purpose_status"])
    if purpose == "missing":
        return _deny(policy, "purpose_required")
    if purpose != "approved":
        return _deny(policy, "purpose_denied")

    consent_requirement = _text(context["consent_requirement"])
    consent_status = _text(context["consent_status"])
    if _text(context["evidence_sensitivity"]) not in {"high", "critical"}:
        return _deny(policy, "not_available")
    if consent_status not in policy.recognized_consent_statuses:
        return _deny(policy, "consent_required")
    if consent_requirement == "required":
        if consent_status == "blocked":
            return _deny(policy, "consent_denied")
        if consent_status != "allowed":
            return _deny(policy, "consent_required")
    elif consent_requirement != "not_required":
        return _deny(policy, "consent_required")

    evidence_state = _text(context["evidence_state"])
    if evidence_state not in policy.recognized_states:
        return _deny(policy, "not_available")
    state_reasons = {
        "missing": "not_found",
        "pending_upload": "upload_pending",
        "quarantined": "quarantined",
        "delete_pending": "not_available",
        "deleted": "deleted",
    }
    if evidence_state not in policy.readable_states:
        return _deny(policy, state_reasons.get(evidence_state, "not_available"))

    if context["retention_status"] != "active":
        return _deny(policy, "retention_expired")
    if _text(context["legal_hold_status"]) not in policy.recognized_legal_hold_statuses:
        return _deny(policy, "legal_hold_unresolved")
    reason_code = _text(context["reason_code"])
    if action.reason_code_required:
        if not reason_code:
            return _deny(policy, "reason_required")
        if reason_code not in policy.access_reason_codes:
            return _deny(policy, "reason_invalid")

    try:
        ttl = _signed_ttl(context, policy, action)
    except EvidencePolicyError as error:
        if error.code == policy.reason_codes["ttl_invalid"]:
            return _deny(policy, "ttl_invalid")
        raise

    if requested_action == "export":
        if reason_code not in policy.export_reason_codes:
            return _deny(policy, "reason_invalid")
        if context["export_approval_status"] != "approved":
            return _deny(policy, "export_approval_required")
        if _text(context["export_recipient_status"]) not in policy.export_recipient_controls:
            return _deny(policy, "export_recipient_invalid")
        artifact_ttl = _optional_integer(context["export_artifact_ttl_seconds"])
        if (
            artifact_ttl is None
            or artifact_ttl < 1
            or artifact_ttl > policy.export_artifact_hard_max_ttl_seconds
        ):
            return _deny(policy, "export_artifact_ttl_invalid")

    return AccessDecision(
        decision="allow",
        reason_code=policy.reason_codes["access_allowed"],
        public_error="",
        ttl_seconds=ttl,
    )


def validate_fixture(document: dict[str, object], policy: EvidenceAccessPolicy) -> int:
    if set(document) != {
        "_fixture",
        "policy_version",
        "opaque_references",
        "default_context",
        "cases",
    }:
        _fail()
    if (
        document["_fixture"] != SYNTHETIC_MARKER
        or document["policy_version"] != policy.policy_version
    ):
        _fail()
    references = _mapping(document["opaque_references"])
    if not references or any(
        not key.endswith("_id") or not _text(value).startswith("test_")
        for key, value in references.items()
    ):
        _fail()

    default_context = _mapping(document["default_context"])
    if set(default_context) != CONTEXT_FIELDS:
        _fail()
    cases = _list(document["cases"])
    if len(cases) < 40:
        _fail()
    case_codes: set[str] = set()
    for item in cases:
        case = _mapping(item)
        if set(case) != {
            "case_code",
            "overrides",
            "expected_decision",
            "expected_reason_code",
            "expected_public_error",
            "expected_ttl_seconds",
        }:
            _fail()
        case_code = _text(case["case_code"])
        if CASE_CODE.fullmatch(case_code) is None or case_code in case_codes:
            _fail()
        case_codes.add(case_code)
        overrides = _mapping(case["overrides"])
        if not set(overrides) <= CONTEXT_FIELDS:
            _fail()
        context = dict(default_context)
        context.update(overrides)
        actual = evaluate_access(context, policy)
        expected_ttl = _optional_integer(case["expected_ttl_seconds"])
        if (
            actual.decision != _text(case["expected_decision"])
            or actual.reason_code != _text(case["expected_reason_code"])
            or actual.public_error != _text(case["expected_public_error"])
            or actual.ttl_seconds != expected_ttl
        ):
            _fail()
    return len(cases)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        policy = validate_policy(_load_json(repo_root / POLICY_PATH))
        case_count = validate_fixture(_load_json(repo_root / FIXTURE_PATH), policy)
    except EvidencePolicyError as error:
        print(f"evidence_access_policy=FAIL code={error.code}", file=sys.stderr)
        return 1
    print("evidence_access_policy=PASS")
    print(f"policy_version={policy.policy_version}")
    print("runtime_activation=BLOCKED_PENDING_NAMED_APPROVALS")
    print(f"synthetic_cases_checked={case_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
