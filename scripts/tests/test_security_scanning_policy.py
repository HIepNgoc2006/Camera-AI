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
from scripts.test_security_scanners_canary import _inspect_opengrep_report

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


def test_clean_opengrep_report_passes_without_exposing_report_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "opengrep.json"
    report.write_text('{"results": [], "errors": []}', encoding="utf-8")

    assert _inspect_opengrep_report(report, 0, tmp_path) == 0
    assert capsys.readouterr().out == (
        "opengrep_gate=PASS scanner_status=0 findings=0 errors=0 report_discarded=true\n"
    )


def test_opengrep_parse_error_fails_with_sanitized_metadata_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "opengrep.json"
    report.write_text(
        '{"results": [], "errors": ['
        '{"path": "services/example.py", "type": "Partial parsing", '
        '"message": "private source excerpt"}]}',
        encoding="utf-8",
    )

    assert _inspect_opengrep_report(report, 3, tmp_path) == 1
    output = capsys.readouterr().out
    assert "opengrep_gate=FAIL scanner_status=3 findings=0 errors=1" in output
    assert "path=services/example.py type=Partial_parsing" in output
    assert "private source excerpt" not in output


def test_opengrep_report_does_not_disclose_outside_workspace_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "opengrep.json"
    report.write_text(
        '{"results": [], "errors": [{"path": "../secret.py", "type": "Parse"}]}',
        encoding="utf-8",
    )

    assert _inspect_opengrep_report(report, 3, tmp_path) == 1
    output = capsys.readouterr().out
    assert "path=outside_workspace type=Parse" in output
    assert "secret.py" not in output
