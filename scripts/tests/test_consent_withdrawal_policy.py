from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_consent_withdrawal_policy import (
    EXPECTED_STORES,
    FIXTURE_PATH,
    POLICY_PATH,
    WITHDRAWAL_POLICY_INVALID,
    WithdrawalPolicyError,
    evaluate_withdrawal,
    validate_fixture,
    validate_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _document(path: Path) -> dict[str, object]:
    value: object = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return value


def _default_context() -> dict[str, object]:
    fixture = _document(FIXTURE_PATH)
    value = fixture["default_context"]
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return dict(value)


def test_repository_policy_and_all_synthetic_cases_are_compatible() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    assert validate_fixture(_document(FIXTURE_PATH), policy) == 95


def test_effective_withdrawal_requires_deny_before_dispose() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    allowed = _default_context()
    allowed.update(
        {
            "operation": "make_effective",
            "current_state": "identity_verified",
            "transition_to": "effective",
        }
    )
    denied = dict(allowed)
    denied["deny_committed_before_disposal"] = False

    assert evaluate_withdrawal(policy, allowed).reason_code == ("WITHDRAWAL_EFFECTIVE_ALLOWED")
    assert evaluate_withdrawal(policy, denied).reason_code == (
        "WITHDRAWAL_DENY_BEFORE_DISPOSE_MISSING"
    )


def test_effective_denial_survives_hold_basis_partial_and_supersession() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    for state in (
        "effective",
        "propagating",
        "partially_completed",
        "completed",
        "superseded",
    ):
        context = _default_context()
        context.update(
            {
                "operation": "processing_access",
                "current_state": state,
                "transition_to": state,
                "legal_hold_active": True,
                "lawful_basis_active": True,
            }
        )

        decision = evaluate_withdrawal(policy, context)

        assert decision.decision == "deny"
        assert decision.reason_code == "WITHDRAWAL_PROCESSING_DENIED"


def test_cross_scope_and_relationship_denials_share_concealed_response() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    wrong_relationship = _default_context()
    wrong_relationship["actor_relationship"] = "unrelated_subject"
    direct_subject = _default_context()
    direct_subject["subject_scope_match"] = False

    relationship_decision = evaluate_withdrawal(policy, wrong_relationship)
    scope_decision = evaluate_withdrawal(policy, direct_subject)

    assert relationship_decision.public_error == "WITHDRAWAL_REQUEST_NOT_FOUND"
    assert scope_decision.public_error == "WITHDRAWAL_REQUEST_NOT_FOUND"


def test_destructive_disposition_requires_explicit_flag_and_change_record() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    missing_flag = _default_context()
    missing_flag.update(
        {
            "operation": "propagate",
            "current_state": "effective",
            "transition_to": "propagating",
            "store_class": "private_evidence_object",
            "canonical_owner": "evidence_service",
            "disposition": "delete_exact_media_or_reference",
        }
    )
    missing_record = dict(missing_flag)
    missing_record["destructive_execution_requested"] = True
    missing_record["physical_disposition_requested"] = True
    missing_record["destructive_change_record_status"] = "missing"

    assert evaluate_withdrawal(policy, missing_flag).reason_code == (
        "WITHDRAWAL_CHANGE_RECORD_REQUIRED"
    )
    assert evaluate_withdrawal(policy, missing_record).reason_code == (
        "WITHDRAWAL_CHANGE_RECORD_REQUIRED"
    )


def test_legal_hold_pauses_only_exact_physical_disposition() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    context = _default_context()
    context.update(
        {
            "operation": "propagate",
            "current_state": "effective",
            "transition_to": "propagating",
            "store_class": "private_evidence_object",
            "canonical_owner": "evidence_service",
            "disposition": "delete_exact_media_or_reference",
            "destructive_execution_requested": True,
            "physical_disposition_requested": True,
            "legal_hold_active": True,
        }
    )

    decision = evaluate_withdrawal(policy, context)

    assert decision.decision == "deny"
    assert decision.reason_code == "WITHDRAWAL_DISPOSITION_PAUSED_LEGAL_HOLD"
    assert decision.public_error == "WITHDRAWAL_PROCESSING_PENDING"


def test_stale_restore_blocks_completion_but_authorized_reconcile_resumes() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    complete = _default_context()
    complete.update(
        {
            "operation": "complete",
            "current_state": "partially_completed",
            "transition_to": "completed",
            "restore_reapply_pending": True,
        }
    )
    reconcile = _default_context()
    reconcile.update(
        {
            "operation": "reconcile",
            "current_state": "partially_completed",
            "transition_to": "propagating",
            "store_class": "backup_restore_reapplication_index",
            "canonical_owner": "backup_restore_owner",
            "restore_reapply_pending": True,
        }
    )

    assert evaluate_withdrawal(policy, complete).reason_code == (
        "WITHDRAWAL_RESTORE_REAPPLY_PENDING"
    )
    assert evaluate_withdrawal(policy, reconcile).reason_code == (
        "WITHDRAWAL_RECONCILIATION_ALLOWED"
    )


def test_owner_matrix_has_exact_actions_without_cross_owner_deletion() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    assert set(policy.stores) == set(EXPECTED_STORES)
    assert len(policy.stores) == 15
    assert all(store.canonical_owner for store in policy.stores.values())
    assert {store.disposition for store in policy.stores.values()} <= policy.dispositions


def test_completion_and_audit_exclude_deleted_or_sensitive_content() -> None:
    document = _document(POLICY_PATH)
    completion = document["completion_evidence"]
    audit = document["audit"]
    assert isinstance(completion, dict)
    assert isinstance(audit, dict)
    completion_required = set(completion["required_fields"])
    completion_forbidden = set(completion["forbidden_fields"])
    audit_required = set(audit["required_fields"])
    audit_forbidden = set(audit["forbidden_fields"])

    sensitive = {
        "subject_name",
        "guardian_name",
        "biometric_reference",
        "face_embedding",
        "face_image",
        "media_binary",
        "signed_url",
        "object_key",
        "provider_identifier",
        "device_token",
        "credential",
        "raw_ansvis_payload",
        "database_row",
        "backup_content",
        "free_form_note",
    }
    assert not completion_required & completion_forbidden
    assert not audit_required & audit_forbidden
    assert sensitive <= completion_forbidden
    assert sensitive <= audit_forbidden


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("runtime_activation", "status"), "active"),
        (
            ("state_transitions", "requested"),
            ["identity_verified", "effective", "rejected", "superseded"],
        ),
        (
            ("authority_matrix", "parent_guardian", "allowed_subject_types"),
            ["student", "staff"],
        ),
        (
            ("owner_disposition_matrix", "private_evidence_object", "disposition"),
            "retain_restricted_proof",
        ),
        (
            (
                "legal_hold_and_lawful_basis",
                "legal_hold_never_grants_consent_processing_access_decrypt_or_export",
            ),
            False,
        ),
        (
            ("completion_evidence", "forbidden_fields"),
            [
                field
                for field in sorted(
                    {
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
                )
            ],
        ),
    ],
)
def test_v1_policy_cannot_broaden_without_a_new_version(
    path: tuple[str, ...],
    replacement: object,
) -> None:
    modified = copy.deepcopy(_document(POLICY_PATH))
    target: object = modified
    for key in path[:-1]:
        assert isinstance(target, dict)
        target = target[key]
    assert isinstance(target, dict)
    target[path[-1]] = replacement

    with pytest.raises(WithdrawalPolicyError, match=WITHDRAWAL_POLICY_INVALID):
        validate_policy(modified)
