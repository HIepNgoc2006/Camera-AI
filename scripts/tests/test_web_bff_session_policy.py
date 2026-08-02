from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from scripts.check_web_bff_session_policy import (
    REQUIRED_FORBIDDEN_OBSERVABILITY,
    evaluate_case,
    load_documents,
    validate_documents,
    validate_implementation,
)

ROOT = Path(__file__).resolve().parents[2]


def _documents() -> tuple[dict[str, Any], dict[str, Any]]:
    return load_documents(ROOT)


def test_policy_and_synthetic_matrix_pass() -> None:
    policy, fixture = _documents()

    assert validate_documents(policy, fixture) == []
    assert validate_implementation(ROOT) == []


def test_every_synthetic_case_has_the_expected_decision() -> None:
    _, fixture = _documents()
    cases = cast(list[dict[str, Any]], fixture["cases"])

    assert cases
    for case in cases:
        assert evaluate_case(case, REQUIRED_FORBIDDEN_OBSERVABILITY) == case["expected_decision"]


def test_browser_token_custody_regression_is_rejected() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(policy)
    cast(dict[str, Any], mutated["token_custody"])["browser_storage_allowed"] = True

    assert "token custody browser_storage_allowed" in validate_documents(mutated, fixture)


def test_cookie_downgrade_regression_is_rejected() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(policy)
    cast(dict[str, Any], mutated["session_cookie"])["http_only"] = False

    assert "cookie HttpOnly" in validate_documents(mutated, fixture)


def test_web_cannot_bypass_api_gateway_boundary() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(policy)
    boundaries = cast(dict[str, Any], mutated["trust_boundaries"])
    gateway = cast(dict[str, Any], boundaries["api_gateway"])
    gateway["owns"] = []

    assert "API Gateway only backend entrypoint" in validate_documents(mutated, fixture)


def test_csrf_origin_authority_cannot_be_client_supplied() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(policy)
    csrf = cast(dict[str, Any], mutated["csrf_and_origin"])
    csrf["allowed_origin_source"] = "client_supplied_origin"

    assert "same-origin authority" in validate_documents(mutated, fixture)


def test_web_cannot_copy_or_invent_timeout_duration() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(policy)
    cast(dict[str, Any], mutated["timeout_contract"])["warning_after_seconds"] = 60

    assert "timeout contract contains no numeric value" in validate_documents(mutated, fixture)


def test_cookie_clear_cannot_claim_server_revocation() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(policy)
    refresh = cast(dict[str, Any], mutated["refresh_and_revocation"])
    refresh["clear_cookie_without_confirmed_revoke"] = "revocation_success"

    assert "local clear is not revocation success" in validate_documents(mutated, fixture)


def test_required_negative_canary_cannot_disappear() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(fixture)
    cases = cast(list[dict[str, Any]], mutated["cases"])
    mutated["cases"] = [case for case in cases if case["case_id"] != "test_token_logging"]

    assert "fixture canary coverage" in validate_documents(policy, mutated)


def test_required_canary_cannot_move_to_an_unrelated_control_category() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(fixture)
    cases = cast(list[dict[str, Any]], mutated["cases"])
    token_logging = next(case for case in cases if case["case_id"] == "test_token_logging")
    token_logging["category"] = "cookie"
    token_logging["input"] = {
        "http_only": False,
        "secure": True,
        "same_site": "Strict",
        "host_only": True,
    }
    token_logging["expected_decision"] = "reject"

    assert "fixture canary category test_token_logging" in validate_documents(policy, mutated)


def test_fixture_marker_is_required() -> None:
    policy, fixture = _documents()
    mutated = deepcopy(fixture)
    mutated["_fixture"] = "UNTRUSTED"

    assert "synthetic fixture marker" in validate_documents(policy, mutated)
