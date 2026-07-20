from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_time_policy import (
    FIXTURE_PATH,
    POLICY_PATH,
    TIME_FRACTION_PRECISION,
    TIME_OFFSET_UNKNOWN,
    TIME_POLICY_INVALID,
    TIME_TIMESTAMP_NAIVE,
    TimePolicyError,
    clock_health_state,
    parse_rfc3339,
    validate_fixture,
    validate_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _document(path: Path) -> dict[str, object]:
    value: object = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return value


def test_repository_policy_and_all_synthetic_cases_are_compatible() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    assert validate_fixture(_document(FIXTURE_PATH), policy) == 20


def test_v1_threshold_boundaries_are_stable() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    assert clock_health_state(-1, policy) == "healthy"
    assert clock_health_state(1.001, policy) == "warning"
    assert clock_health_state(-5, policy) == "warning"
    assert clock_health_state(5.001, policy) == "critical"


@pytest.mark.parametrize(
    ("value", "error_code"),
    [
        ("2026-01-15T08:30:00", TIME_TIMESTAMP_NAIVE),
        ("2026-01-15T08:30:00-00:00", TIME_OFFSET_UNKNOWN),
        ("2026-01-15T08:30:00.1234567Z", TIME_FRACTION_PRECISION),
    ],
)
def test_strict_timestamp_profile_rejects_ambiguous_inputs(value: str, error_code: str) -> None:
    with pytest.raises(TimePolicyError, match=error_code):
        parse_rfc3339(value, 6)


def test_v1_policy_cannot_change_threshold_without_a_versioned_contract() -> None:
    modified = copy.deepcopy(_document(POLICY_PATH))
    health = modified["clock_health"]
    assert isinstance(health, dict)
    health["critical_offset_seconds"] = 10

    with pytest.raises(TimePolicyError, match=TIME_POLICY_INVALID):
        validate_policy(modified)
