from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.npm_audit_gate import EXIT_CLEAN, EXIT_VIOLATIONS, main

FAR_FUTURE = "2099-01-01"


def _registry_entry(
    exception_id: str, finding_id: str, expires_on: str = FAR_FUTURE
) -> dict[str, str]:
    return {
        "exception_id": exception_id,
        "finding_id": finding_id,
        "owner": "repository-owner",
        "justification": "test justification",
        "compensating_control": "test control",
        "approved_by": "repository-owner",
        "expires_on": expires_on,
    }


def _write_registry(path: Path, entries: list[dict[str, str]]) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, "exceptions": entries}, indent=2), encoding="utf-8"
    )


def _write_audit(path: Path, vulnerabilities: dict[str, Any], metadata: dict[str, Any]) -> None:
    document: dict[str, Any] = {"auditReportVersion": 2, "vulnerabilities": vulnerabilities}
    document["metadata"] = metadata
    path.write_text(json.dumps(document), encoding="utf-8")


def _run(
    tmp_path: Path, audit_vulnerabilities: dict[str, Any], entries: list[dict[str, str]]
) -> int:
    audit_path = tmp_path / "audit.json"
    registry_path = tmp_path / "registry.json"
    _write_audit(audit_path, audit_vulnerabilities, {"vulnerabilities": {"high": 0, "critical": 0}})
    _write_registry(registry_path, entries)
    return main(["--audit-json", str(audit_path), "--registry", str(registry_path)])


def _braces_audit() -> dict[str, Any]:
    return {
        "braces": {
            "via": [
                {
                    "url": "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm",
                    "severity": "high",
                }
            ]
        }
    }


def _invoke_with_bad_audit(
    tmp_path: Path, raw: str, entries: list[dict[str, str]]
) -> tuple[int, str]:
    audit_path = tmp_path / "audit.json"
    registry_path = tmp_path / "registry.json"
    audit_path.write_text(raw, encoding="utf-8")
    _write_registry(registry_path, entries)
    code = main(["--audit-json", str(audit_path), "--registry", str(registry_path)])
    assert code in {EXIT_CLEAN, EXIT_VIOLATIONS}
    return code, "invoked"


def test_clean_report_passes(tmp_path: Path) -> None:
    code = _run(tmp_path, {}, [])
    assert code == EXIT_CLEAN


def test_high_without_exception_fails(tmp_path: Path) -> None:
    code = _run(tmp_path, _braces_audit(), [])
    assert code == EXIT_VIOLATIONS


def test_reviewed_exception_suppresses_high(tmp_path: Path) -> None:
    entries = [_registry_entry("SEC-NPM-BRACES-001", "GHSA-vfj7-8cjw-p6xm")]
    code = _run(tmp_path, _braces_audit(), entries)
    assert code == EXIT_CLEAN


def test_critical_is_never_suppressible(tmp_path: Path) -> None:
    audit = {
        "next": {
            "via": [
                {
                    "url": "https://github.com/advisories/GHSA-vcvr-r3jv-pc5j",
                    "severity": "critical",
                }
            ]
        }
    }
    entries = [_registry_entry("SEC-NPM-NEXT-001", "GHSA-vcvr-r3jv-pc5j")]
    code = _run(tmp_path, audit, entries)
    assert code == EXIT_VIOLATIONS


def test_expired_exception_fails_closed(tmp_path: Path) -> None:
    entries = [
        _registry_entry("SEC-NPM-BRACES-OLD", "GHSA-vfj7-8cjw-p6xm", expires_on="2000-01-01")
    ]
    code = _run(tmp_path, _braces_audit(), entries)
    assert code == EXIT_VIOLATIONS


def test_non_ghsa_registry_entries_are_ignored(tmp_path: Path) -> None:
    entries = [_registry_entry("SEC-PY-001", "PYSEC-2026-4150")]
    code = _run(tmp_path, _braces_audit(), entries)
    assert code == EXIT_VIOLATIONS


def test_missing_vulnerabilities_fails_closed(tmp_path: Path) -> None:
    code, _ = _invoke_with_bad_audit(tmp_path, json.dumps({"metadata": {}}), [])
    assert code == EXIT_VIOLATIONS


def test_via_string_references_are_skipped(tmp_path: Path) -> None:
    audit: dict[str, Any] = {
        "micromatch": {"via": ["braces"]},
        "braces": {
            "via": [
                {
                    "url": "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm",
                    "severity": "high",
                }
            ]
        },
    }
    entries = [_registry_entry("SEC-NPM-BRACES-002", "GHSA-vfj7-8cjw-p6xm")]
    code = _run(tmp_path, audit, entries)
    assert code == EXIT_CLEAN


def test_unreadable_audit_report_fails_closed(tmp_path: Path) -> None:
    code, _ = _invoke_with_bad_audit(tmp_path, "not json at all", [])
    assert code == EXIT_VIOLATIONS


def test_gate_module_exposes_expected_exit_codes() -> None:
    assert EXIT_CLEAN == 0
    assert EXIT_VIOLATIONS == 1


def test_gate_script_is_mypy_strict_clean() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "scripts/npm_audit_gate.py",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
