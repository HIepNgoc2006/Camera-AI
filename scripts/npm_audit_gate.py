"""Fail-closed gate over the Web Portal npm audit report.

The gate re-evaluates a captured ``npm audit --json`` report instead of
trusting npm's exit code alone. An advisory is suppressible only when a
reviewed, unexpired entry in the shared security exception registry
(``packages/security-scanning-policy/security-scanning-exceptions-v1.json``)
covers its GHSA identifier and the advisory is not critical. Registry
entries whose ``finding_id`` does not start with ``GHSA-`` belong to other
scanners and are ignored here. Every other advisory, a critical severity,
an unreadable report, an expired exception, or registry misuse fails
closed with stable sanitized messages.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1

ADVISORY_ID = re.compile(r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}", re.IGNORECASE)

Registry = Mapping[str, tuple[str, str]]


class GateError(ValueError):
    """A stable, sanitized npm-audit gate failure."""


def _load_json_object(path: Path, error_prefix: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise GateError(f"{error_prefix}: unreadable file ({exc.__class__.__name__})") from exc
    except json.JSONDecodeError:
        raise GateError(f"{error_prefix}: content is not valid JSON") from None
    if not isinstance(value, dict):
        raise GateError(f"{error_prefix}: expected a JSON object")
    return value


def load_npm_exceptions(path: Path, today: date) -> Registry:
    """Return the reviewed GHSA exceptions keyed by advisory identifier."""

    document = _load_json_object(path, "EXCEPTION_REGISTRY")
    entries = document.get("exceptions")
    if not isinstance(entries, list):
        raise GateError("EXCEPTION_REGISTRY: exceptions must be a list")
    covered: dict[str, tuple[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise GateError("EXCEPTION_REGISTRY: entry must be an object")
        exception_id = entry.get("exception_id")
        finding_id = entry.get("finding_id")
        expires_on = entry.get("expires_on")
        if (
            not isinstance(exception_id, str)
            or not exception_id.strip()
            or not isinstance(finding_id, str)
            or not finding_id.strip()
            or not isinstance(expires_on, str)
            or not expires_on.strip()
        ):
            raise GateError(f"EXCEPTION_REGISTRY: entry {exception_id!r} has invalid fields")
        if not finding_id.startswith("GHSA-"):
            continue
        try:
            expiry = date.fromisoformat(expires_on)
        except ValueError:
            raise GateError(
                f"EXCEPTION_REGISTRY: {exception_id} expiry is not an ISO date"
            ) from None
        if expiry < today:
            raise GateError(f"EXCEPTION_REGISTRY: {exception_id} expired on {expires_on}")
        if finding_id in covered:
            raise GateError(f"EXCEPTION_REGISTRY: {finding_id} is covered by multiple exceptions")
        covered[finding_id] = (exception_id, expiry.isoformat())
    return covered


def evaluate_audit(
    audit: Mapping[str, Any],
    covered: Registry,
) -> tuple[list[str], list[str], dict[str, int]]:
    """Return (violations, suppressions, totals) for one audit report."""

    vulnerabilities = audit.get("vulnerabilities")
    if vulnerabilities is None:
        raise GateError("AUDIT_REPORT: missing vulnerabilities mapping")
    if not isinstance(vulnerabilities, dict):
        raise GateError("AUDIT_REPORT: vulnerabilities must be an object")

    violations: list[str] = []
    suppressions: list[str] = []
    seen: set[tuple[str, str]] = set()
    for package, item in vulnerabilities.items():
        if not isinstance(item, dict):
            raise GateError(f"AUDIT_REPORT: package {package} entry must be an object")
        via_items = item.get("via")
        if not isinstance(via_items, list):
            raise GateError(f"AUDIT_REPORT: package {package} via must be a list")
        for via in via_items:
            if isinstance(via, str):
                # Reference to another flagged package; its advisory is
                # evaluated at the package that owns it.
                continue
            if not isinstance(via, dict):
                raise GateError(f"AUDIT_REPORT: package {package} via entry must be an object")
            url = via.get("url")
            severity = via.get("severity")
            if not isinstance(url, str) or not isinstance(severity, str):
                raise GateError(f"AUDIT_REPORT: package {package} advisory is malformed")
            advisory_match = ADVISORY_ID.search(url)
            if advisory_match is None:
                raise GateError(f"AUDIT_REPORT: package {package} advisory has no GHSA identifier")
            advisory_id = advisory_match.group(0)
            if (package, advisory_id) in seen:
                continue
            seen.add((package, advisory_id))
            if severity == "critical":
                violations.append(
                    f"package={package} advisory={advisory_id} severity=critical never_suppressible"
                )
                continue
            exception = covered.get(advisory_id)
            if exception is None:
                violations.append(
                    f"package={package} advisory={advisory_id} severity={severity} no_reviewed_exception"
                )
            else:
                suppressions.append(
                    f"package={package} advisory={advisory_id} severity={severity} "
                    f"exception={exception[0]} expires_on={exception[1]}"
                )

    metadata = audit.get("metadata")
    totals: dict[str, int] = {}
    if isinstance(metadata, dict) and isinstance(metadata.get("vulnerabilities"), dict):
        raw_totals = metadata["vulnerabilities"]
        totals = {key: int(value) for key, value in raw_totals.items() if isinstance(value, int)}
    return violations, suppressions, totals


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed gate over one npm audit JSON report.")
    parser.add_argument(
        "--audit-json", required=True, type=Path, help="npm audit --json report path"
    )
    parser.add_argument(
        "--registry",
        required=True,
        type=Path,
        help="security-scanning-exceptions-v1.json path",
    )
    args = parser.parse_args(argv)

    try:
        audit = _load_json_object(args.audit_json, "AUDIT_REPORT")
        covered = load_npm_exceptions(args.registry, date.today())
        violations, suppressions, totals = evaluate_audit(audit, covered)
    except GateError as exc:
        print(f"npm_audit_gate=fail_closed error={exc}")
        return EXIT_VIOLATIONS

    for line in suppressions:
        print(f"suppressed {line}")
    for line in violations:
        print(f"violation {line}")
    totals_text = " ".join(f"{key}={value}" for key, value in sorted(totals.items()))
    print(
        f"npm_audit_gate={'clean' if not violations else 'violations'} "
        f"suppressions={len(suppressions)} violations={len(violations)} {totals_text}".rstrip()
    )
    return EXIT_VIOLATIONS if violations else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
