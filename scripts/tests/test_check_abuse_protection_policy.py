from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

from scripts.check_abuse_protection_policy import run_checks

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "packages/abuse-protection-policy/abuse-protection-policy-v1.json"


def _policy() -> dict[str, Any]:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_abuse_protection_policy_matches_authoritative_baselines() -> None:
    assert run_checks() == []


def test_checker_rejects_rate_limit_drift() -> None:
    policy = copy.deepcopy(_policy())
    policy["controls"]["api_gateway"]["rate_limit_buckets"]["login"]["burst"] = 11

    assert "API rate-limit bucket drift" in run_checks(policy)


def test_checker_rejects_missing_surface_and_issue_owner() -> None:
    policy = copy.deepcopy(_policy())
    policy["scope"].remove("object_storage_delivery")
    del policy["implementation_issue_mapping"]["89"]

    findings = run_checks(policy)
    assert "required surface set drift" in findings
    assert "mitigation issue mapping drift" in findings


def test_checker_rejects_unsafe_evidence_and_public_storage() -> None:
    policy = copy.deepcopy(_policy())
    policy["monitoring_evidence"]["forbidden_dimensions"].remove("signed_url")
    policy["monitoring_evidence"]["raw_request_capture_allowed"] = True
    policy["controls"]["object_storage_delivery"]["bucket_visibility"] = "public"

    findings = run_checks(policy)
    assert "safe evidence forbidden-dimension set is incomplete" in findings
    assert "raw request capture must be disabled" in findings
    assert "object storage must remain private" in findings
