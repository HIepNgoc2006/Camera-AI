"""Validate the repository's fail-closed software supply-chain scanning policy."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from datetime import date
from pathlib import Path

POLICY_PATH = Path("packages/security-scanning-policy/security-scanning-policy-v1.json")
EXCEPTIONS_PATH = Path("packages/security-scanning-policy/security-scanning-exceptions-v1.json")
AUDIT_REQUIREMENTS_PATH = Path("requirements-security-audit.txt")
TOOL_REQUIREMENTS_PATH = Path("requirements-security-tools.txt")
QUALITY_REQUIREMENTS_PATH = Path("requirements-quality.txt")
WORKFLOW_PATH = Path(".github/workflows/security-scanning.yml")
DEPENDABOT_PATH = Path(".github/dependabot.yml")
SEMGREP_RULES_PATH = Path(".semgrep/security.yml")

PIN_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)(?P<extras>\[[A-Za-z0-9_,.-]+\])?"
    r"==(?P<version>[A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)
REQUIRED_TOOLS = {
    "bandit": "1.9.4",
    "pip-audit": "2.10.1",
}
OPENGREP_VERSION = "1.22.0"
OPENGREP_LINUX_SHA256 = "45bcd58440e397ed52c50e953ccf5948909ea77087c9186fc7d277216f62e319"
SEMGREP_RULES_SHA256 = "f5f3fd551bf6e7b57fc349cc58e77b9baad6cafb2c6c53c85e34d5bd17677b8d"
REQUIRED_EXCEPTION_FIELDS = {
    "exception_id",
    "finding_id",
    "owner",
    "justification",
    "compensating_control",
    "approved_by",
    "expires_on",
}


class PolicyError(ValueError):
    """A stable, sanitized security-policy validation failure."""


def _normalized_name(requirement: str) -> str:
    match = PIN_PATTERN.fullmatch(requirement)
    if match is None:
        raise PolicyError("SECURITY_DEPENDENCY_NOT_EXACTLY_PINNED")
    return re.sub(r"[-_.]+", "-", match.group("name")).lower()


def _require_exact_pin(requirement: str) -> str:
    if ";" in requirement or "@" in requirement or PIN_PATTERN.fullmatch(requirement) is None:
        raise PolicyError("SECURITY_DEPENDENCY_NOT_EXACTLY_PINNED")
    return requirement


def _requirements_file(path: Path) -> list[str]:
    if not path.is_file():
        raise PolicyError("SECURITY_REQUIREMENTS_FILE_MISSING")
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(_require_exact_pin(line))
    return lines


def _pyproject_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory in ("packages", "services", "workers"):
        base = repo_root / directory
        if base.is_dir():
            paths.extend(base.glob("*/pyproject.toml"))
    return sorted(paths)


def expected_audit_requirements(repo_root: Path) -> list[str]:
    """Return sorted external direct pins declared by code and security tooling."""

    pyprojects = _pyproject_paths(repo_root)
    if not pyprojects:
        raise PolicyError("SECURITY_PYPROJECTS_MISSING")

    documents: list[dict[str, object]] = []
    internal_names: set[str] = set()
    for path in pyprojects:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        documents.append(document)
        project = document.get("project")
        if isinstance(project, dict) and isinstance(project.get("name"), str):
            internal_names.add(re.sub(r"[-_.]+", "-", str(project["name"])).lower())

    requirements: dict[str, str] = {}

    def add(values: Iterable[object]) -> None:
        for value in values:
            if not isinstance(value, str):
                raise PolicyError("SECURITY_DEPENDENCY_DECLARATION_INVALID")
            pin = _require_exact_pin(value)
            if _normalized_name(pin) in internal_names:
                continue
            key = pin.split("==", maxsplit=1)[0].lower()
            existing = requirements.get(key)
            if existing is not None and existing != pin:
                raise PolicyError("SECURITY_DEPENDENCY_VERSION_CONFLICT")
            requirements[key] = pin

    for document in documents:
        build_system = document.get("build-system")
        if isinstance(build_system, dict):
            requires = build_system.get("requires", [])
            if isinstance(requires, list):
                add(requires)

        project = document.get("project")
        if not isinstance(project, dict):
            raise PolicyError("SECURITY_PROJECT_METADATA_INVALID")
        dependencies = project.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise PolicyError("SECURITY_DEPENDENCY_DECLARATION_INVALID")
        add(dependencies)
        optional = project.get("optional-dependencies", {})
        if not isinstance(optional, dict):
            raise PolicyError("SECURITY_DEPENDENCY_DECLARATION_INVALID")
        for values in optional.values():
            if not isinstance(values, list):
                raise PolicyError("SECURITY_DEPENDENCY_DECLARATION_INVALID")
            add(values)

    add(_requirements_file(repo_root / QUALITY_REQUIREMENTS_PATH))
    add(_requirements_file(repo_root / TOOL_REQUIREMENTS_PATH))
    return sorted(requirements.values(), key=lambda item: (_normalized_name(item), item.casefold()))


def validate_exceptions(document: object, today: date) -> None:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise PolicyError("SECURITY_EXCEPTION_REGISTRY_INVALID")
    exceptions = document.get("exceptions")
    if not isinstance(exceptions, list):
        raise PolicyError("SECURITY_EXCEPTION_REGISTRY_INVALID")

    identifiers: set[str] = set()
    for entry in exceptions:
        if not isinstance(entry, dict) or set(entry) != REQUIRED_EXCEPTION_FIELDS:
            raise PolicyError("SECURITY_EXCEPTION_FIELDS_INVALID")
        if any(not isinstance(entry[field], str) or not entry[field].strip() for field in entry):
            raise PolicyError("SECURITY_EXCEPTION_FIELDS_INVALID")
        exception_id = str(entry["exception_id"])
        if exception_id in identifiers:
            raise PolicyError("SECURITY_EXCEPTION_ID_DUPLICATE")
        identifiers.add(exception_id)
        try:
            expires_on = date.fromisoformat(str(entry["expires_on"]))
        except ValueError as exc:
            raise PolicyError("SECURITY_EXCEPTION_EXPIRY_INVALID") from exc
        if expires_on < today:
            raise PolicyError("SECURITY_EXCEPTION_EXPIRED")


def _load_json(path: Path, missing_code: str) -> object:
    if not path.is_file():
        raise PolicyError(missing_code)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyError("SECURITY_POLICY_JSON_INVALID") from exc


def _tracked_dockerfiles(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--", "Dockerfile", "*/Dockerfile", "*/*/Dockerfile"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise PolicyError("SECURITY_TRACKED_FILE_QUERY_FAILED")
    return [line for line in completed.stdout.splitlines() if line]


def validate_repository(repo_root: Path, today: date | None = None) -> None:
    policy = _load_json(repo_root / POLICY_PATH, "SECURITY_POLICY_MISSING")
    if not isinstance(policy, dict):
        raise PolicyError("SECURITY_POLICY_INVALID")
    if (
        policy.get("policy_id") != "security_scanning_policy_v1"
        or policy.get("schema_version") != 1
        or policy.get("status") != "active"
    ):
        raise PolicyError("SECURITY_POLICY_INVALID")

    merge_gates = policy.get("merge_gates")
    if not isinstance(merge_gates, dict):
        raise PolicyError("SECURITY_MERGE_GATES_INVALID")
    dependency_gate = merge_gates.get("dependency_audit")
    python_gate = merge_gates.get("python_sast")
    filesystem_gate = merge_gates.get("filesystem_scan")
    if not all(isinstance(item, dict) for item in (dependency_gate, python_gate, filesystem_gate)):
        raise PolicyError("SECURITY_MERGE_GATES_INVALID")
    assert isinstance(dependency_gate, dict)
    assert isinstance(python_gate, dict)
    assert isinstance(filesystem_gate, dict)
    if dependency_gate.get("version") != REQUIRED_TOOLS["pip-audit"]:
        raise PolicyError("SECURITY_SCANNER_VERSION_DRIFT")
    sast_versions = {
        item.get("name"): item.get("version")
        for item in python_gate.get("tools", [])
        if isinstance(item, dict)
    }
    if sast_versions != {"bandit": REQUIRED_TOOLS["bandit"]}:
        raise PolicyError("SECURITY_SCANNER_VERSION_DRIFT")
    semgrep_engine = python_gate.get("semgrep_compatible_engine")
    if not isinstance(semgrep_engine, dict) or semgrep_engine != {
        "name": "opengrep",
        "version": OPENGREP_VERSION,
        "linux_binary_sha256": OPENGREP_LINUX_SHA256,
        "rules": ".semgrep/security.yml",
        "rules_sha256": SEMGREP_RULES_SHA256,
        "engine": "oss_only",
        "strict_config": True,
        "version_check": "disabled",
        "remote_config": False,
        "source_upload": False,
    }:
        raise PolicyError("SECURITY_SCANNER_VERSION_DRIFT")
    if (
        filesystem_gate.get("version") != "0.70.0"
        or filesystem_gate.get("linux_archive_sha256")
        != "8b4376d5d6befe5c24d503f10ff136d9e0c49f9127a4279fd110b727929a5aa9"
    ):
        raise PolicyError("SECURITY_SCANNER_VERSION_DRIFT")

    canaries = policy.get("canaries")
    if not isinstance(canaries, dict) or canaries.get("required_scanners") != [
        "pip-audit",
        "bandit",
        "opengrep",
        "trivy",
    ]:
        raise PolicyError("SECURITY_CANARY_POLICY_DRIFT")

    tool_pins = {
        _normalized_name(item): item.split("==", maxsplit=1)[1]
        for item in _requirements_file(repo_root / TOOL_REQUIREMENTS_PATH)
    }
    if tool_pins != REQUIRED_TOOLS:
        raise PolicyError("SECURITY_SCANNER_VERSION_DRIFT")

    expected = expected_audit_requirements(repo_root)
    actual = _requirements_file(repo_root / AUDIT_REQUIREMENTS_PATH)
    if actual != expected:
        raise PolicyError("SECURITY_AUDIT_REQUIREMENTS_DRIFT")

    exceptions = _load_json(repo_root / EXCEPTIONS_PATH, "SECURITY_EXCEPTION_REGISTRY_MISSING")
    validate_exceptions(exceptions, today or date.today())

    for required_path in (WORKFLOW_PATH, DEPENDABOT_PATH, SEMGREP_RULES_PATH):
        if not (repo_root / required_path).is_file():
            raise PolicyError("SECURITY_AUTOMATION_FILE_MISSING")

    rules_text = (repo_root / SEMGREP_RULES_PATH).read_text(encoding="utf-8")
    if hashlib.sha256(rules_text.encode("utf-8")).hexdigest() != SEMGREP_RULES_SHA256:
        raise PolicyError("SECURITY_SAST_RULESET_DRIFT")

    workflow = (repo_root / WORKFLOW_PATH).read_text(encoding="utf-8")
    for token in (
        OPENGREP_LINUX_SHA256,
        "--disable-version-check",
        "--oss-only",
        "--strict",
        ".semgrep/security.yml",
    ):
        if token not in workflow:
            raise PolicyError("SECURITY_OPENGREP_WORKFLOW_DRIFT")

    activation_gates = policy.get("activation_gates")
    if not isinstance(activation_gates, dict):
        raise PolicyError("SECURITY_ACTIVATION_GATES_INVALID")
    image_gate = activation_gates.get("container_image_scan_and_sbom")
    if not isinstance(image_gate, dict):
        raise PolicyError("SECURITY_ACTIVATION_GATES_INVALID")
    if _tracked_dockerfiles(repo_root) and image_gate.get("status") != "active":
        raise PolicyError("SECURITY_IMAGE_SCAN_ACTIVATION_REQUIRED")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        validate_repository(repo_root)
    except PolicyError as exc:
        print(f"security_scanning_policy=FAIL code={exc}", file=sys.stderr)
        return 1
    print("security_scanning_policy=PASS")
    print(f"python_direct_pins={len(expected_audit_requirements(repo_root))}")
    print("exceptions=valid")
    print("activation_gates=fail_closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
