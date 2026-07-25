from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_notification_privacy_policy import (
    FIXTURE_PATH,
    NOTIFICATION_POLICY_INVALID,
    POLICY_PATH,
    NotificationPolicyError,
    evaluate_notification,
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

    assert validate_fixture(_document(FIXTURE_PATH), policy) == 81


@pytest.mark.parametrize(
    ("channel", "endpoint_status", "protection", "content_fields"),
    [
        (
            "in_app",
            "not_required",
            "not_required",
            [
                "template_code",
                "template_version",
                "generic_title_code",
                "generic_body_code",
                "opaque_notification_ref",
                "opaque_resource_ref",
                "created_at",
                "expires_at",
            ],
        ),
        (
            "push",
            "active",
            "encrypted_tokenized",
            [
                "template_code",
                "template_version",
                "generic_title_code",
                "generic_body_code",
                "opaque_notification_ref",
                "allowlisted_route_code",
                "expires_at",
            ],
        ),
        (
            "email",
            "active",
            "encrypted_endpoint",
            [
                "template_code",
                "template_version",
                "generic_subject_code",
                "generic_body_code",
                "opaque_notification_ref",
                "allowlisted_route_code",
                "expires_at",
            ],
        ),
    ],
)
def test_all_channels_allow_only_the_minimized_contract(
    channel: str,
    endpoint_status: str,
    protection: str,
    content_fields: list[str],
) -> None:
    policy = validate_policy(_document(POLICY_PATH))
    context = _default_context()
    context.update(
        {
            "channel": channel,
            "endpoint_status": endpoint_status,
            "endpoint_protection_status": protection,
            "content_fields": content_fields,
        }
    )

    decision = evaluate_notification(context, policy)

    assert decision.decision == "allow"
    assert decision.reason_code == "NOTIFICATION_DISPATCH_ALLOWED"


def test_prohibited_preview_field_fails_closed() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    context = _default_context()
    content_fields_value = context["content_fields"]
    assert isinstance(content_fields_value, list)
    content_fields = list(content_fields_value)
    content_fields.append("violation_detail")
    context["content_fields"] = content_fields

    decision = evaluate_notification(context, policy)

    assert decision.decision == "deny"
    assert decision.reason_code == "NOTIFICATION_CONTENT_DENIED"
    assert decision.public_error == "NOTIFICATION_REQUEST_INVALID"


def test_wrong_recipient_and_missing_resource_share_public_response() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    wrong_recipient = _default_context()
    wrong_recipient["recipient_relationship"] = "unrelated_child"
    missing = _default_context()
    missing["resource_exists"] = False

    wrong_decision = evaluate_notification(wrong_recipient, policy)
    missing_decision = evaluate_notification(missing, policy)

    assert wrong_decision.public_error == "NOTIFICATION_NOT_FOUND"
    assert missing_decision.public_error == "NOTIFICATION_NOT_FOUND"


def test_notification_open_reauthorizes_current_resource_access() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    context = _default_context()
    context.update(
        {
            "operation": "open",
            "open_resource_authorization_status": "denied",
        }
    )

    decision = evaluate_notification(context, policy)

    assert decision.decision == "deny"
    assert decision.reason_code == "NOTIFICATION_OPEN_REAUTHORIZATION_DENIED"


def test_consent_withdrawal_cancels_instead_of_retrying_delivery() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    retry = _default_context()
    retry.update({"operation": "retry", "consent_status": "withdrawn"})
    cancel = _default_context()
    cancel.update(
        {
            "operation": "cancel",
            "cancellation_trigger": "consent_withdrawn",
        }
    )

    retry_decision = evaluate_notification(retry, policy)
    cancel_decision = evaluate_notification(cancel, policy)

    assert retry_decision.reason_code == "NOTIFICATION_CONSENT_DENIED"
    assert cancel_decision.reason_code == "NOTIFICATION_CANCELLATION_ALLOWED"


def test_audit_contract_excludes_recipient_endpoint_and_sensitive_content() -> None:
    policy_document = _document(POLICY_PATH)
    audit = policy_document["audit"]
    assert isinstance(audit, dict)
    required = set(audit["required_fields"])
    forbidden = set(audit["forbidden_fields"])

    assert not required & forbidden
    assert {
        "email_address",
        "phone_number",
        "device_token",
        "message_text",
        "signed_url",
        "object_key",
        "media_binary",
        "face_embedding",
        "raw_ansvis_payload",
        "access_token",
        "credential",
        "free_form_note",
    } <= forbidden


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("runtime_activation", "status"), "active"),
        (
            ("channels", "push", "allowed_fields"),
            [
                "template_code",
                "template_version",
                "generic_title_code",
                "generic_body_code",
                "opaque_notification_ref",
                "allowlisted_route_code",
                "expires_at",
                "violation_detail",
            ],
        ),
        (
            ("recipient_role_matrix", "parent_guardian", "content_classes"),
            [
                "attendance_update",
                "timekeeping_update",
                "violation_update",
                "correction_update",
                "privacy_action",
            ],
        ),
        (("content_classes", "attendance_update", "template_version"), 2),
        (("endpoint_protection", "device_token_storage"), "plaintext"),
        (
            (
                "expiry_retry_and_dead_letter",
                "dead_letter_payload_allowed_fields",
            ),
            [
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
                "device_token",
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

    with pytest.raises(NotificationPolicyError, match=NOTIFICATION_POLICY_INVALID):
        validate_policy(modified)
