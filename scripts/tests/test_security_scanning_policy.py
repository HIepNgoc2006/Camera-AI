from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.check_security_scanning_policy import (
    PolicyError,
    _require_exact_pin,
    expected_audit_requirements,
    validate_exceptions,
    validate_repository,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repository_security_scanning_policy_is_valid() -> None:
    validate_repository(REPO_ROOT, today=date(2026, 8, 1))


def test_audit_inventory_is_sorted_and_covers_representative_dependencies() -> None:
    requirements = expected_audit_requirements(REPO_ROOT)

    assert requirements.index("httpx==0.28.1") < requirements.index("httpx2==2.7.0")
    assert "fastapi==0.139.0" in requirements
    assert "psycopg[binary]==3.3.4" in requirements
    assert "pip-audit==2.10.1" in requirements


@pytest.mark.parametrize(
    "requirement",
    ("fastapi>=0.139.0", "fastapi", "package @ https://example.invalid/a.whl"),
)
def test_non_exact_dependency_pin_fails_closed(requirement: str) -> None:
    with pytest.raises(PolicyError, match="SECURITY_DEPENDENCY_NOT_EXACTLY_PINNED"):
        _require_exact_pin(requirement)


def test_expired_exception_fails_ci() -> None:
    registry = {
        "schema_version": 1,
        "exceptions": [
            {
                "exception_id": "SEC-EX-001",
                "finding_id": "CVE-SYNTHETIC-0001",
                "owner": "security_ops",
                "justification": "Synthetic test only",
                "compensating_control": "Dependency remains disabled",
                "approved_by": "security_reviewer",
                "expires_on": "2026-07-31",
            }
        ],
    }

    with pytest.raises(PolicyError, match="SECURITY_EXCEPTION_EXPIRED"):
        validate_exceptions(registry, today=date(2026, 8, 1))


def test_empty_exception_registry_is_valid() -> None:
    validate_exceptions({"schema_version": 1, "exceptions": []}, date(2026, 8, 1))
