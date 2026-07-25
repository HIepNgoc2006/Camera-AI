from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_evidence_access_policy import (
    EVIDENCE_POLICY_INVALID,
    FIXTURE_PATH,
    POLICY_PATH,
    EvidencePolicyError,
    evaluate_access,
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

    assert validate_fixture(_document(FIXTURE_PATH), policy) == 53


@pytest.mark.parametrize(("ttl", "expected"), [(None, 60), (1, 1), (60, 60), (300, 300)])
def test_standard_signed_get_boundaries(ttl: int | None, expected: int) -> None:
    policy = validate_policy(_document(POLICY_PATH))
    context = _default_context()
    context.update(
        {
            "requested_action": "view_thumbnail",
            "permission_code": "evidence.view_thumbnail",
            "url_ttl_seconds": ttl,
        }
    )

    decision = evaluate_access(context, policy)

    assert decision.decision == "allow"
    assert decision.ttl_seconds == expected


@pytest.mark.parametrize("ttl", [-1, 0, 301])
def test_standard_signed_get_rejects_invalid_ttl(ttl: int) -> None:
    policy = validate_policy(_document(POLICY_PATH))
    context = _default_context()
    context.update(
        {
            "requested_action": "view_thumbnail",
            "permission_code": "evidence.view_thumbnail",
            "url_ttl_seconds": ttl,
        }
    )

    decision = evaluate_access(context, policy)

    assert decision.decision == "deny"
    assert decision.reason_code == "EVIDENCE_URL_TTL_INVALID"
    assert decision.public_error == "EVIDENCE_ACCESS_INVALID"


def test_unauthorized_and_missing_resources_share_public_response() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    unauthorized = _default_context()
    unauthorized["tenant_scope_match"] = False
    missing = _default_context()
    missing.update({"resource_exists": False, "evidence_state": "missing"})

    unauthorized_decision = evaluate_access(unauthorized, policy)
    missing_decision = evaluate_access(missing, policy)

    assert unauthorized_decision.public_error == "EVIDENCE_NOT_FOUND"
    assert missing_decision.public_error == "EVIDENCE_NOT_FOUND"
    assert unauthorized_decision.reason_code != missing_decision.reason_code


def test_legal_hold_never_restores_expired_access() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    context = _default_context()
    context.update({"retention_status": "expired", "legal_hold_status": "active"})

    decision = evaluate_access(context, policy)

    assert decision.decision == "deny"
    assert decision.reason_code == "EVIDENCE_RETENTION_EXPIRED"


def test_audit_contract_excludes_sensitive_and_delivery_fields() -> None:
    policy_document = _document(POLICY_PATH)
    audit = policy_document["audit"]
    assert isinstance(audit, dict)
    required = set(audit["required_fields"])
    forbidden = set(audit["forbidden_fields"])

    assert not required & forbidden
    assert {
        "signed_url",
        "object_key",
        "media_binary",
        "face_embedding",
        "raw_ansvis_payload",
        "access_token",
        "free_form_note",
    } <= forbidden


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("runtime_activation", "status"), "active"),
        (("signed_get", "profiles", "standard_view", "hard_max_ttl_seconds"), 600),
        (("role_matrix", "system_admin", "candidate_actions"), ["view_original"]),
        (("export", "artifact_hard_max_ttl_seconds"), 1209600),
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

    with pytest.raises(EvidencePolicyError, match=EVIDENCE_POLICY_INVALID):
        validate_policy(modified)
