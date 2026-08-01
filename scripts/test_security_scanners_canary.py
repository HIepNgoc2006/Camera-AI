"""Prove each supply-chain scanner rejects a synthetic runtime-generated canary."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

SCANNERS = ("pip-audit", "bandit", "opengrep", "trivy")


@dataclass(frozen=True)
class CanaryResult:
    status: int
    finding_count: int


def _executable(name: str, explicit: str | None = None) -> str:
    local_name = f"{name}.exe" if sys.platform == "win32" else name
    local_candidate = Path(sys.executable).with_name(local_name)
    candidate = (
        explicit
        or shutil.which(name)
        or (str(local_candidate) if local_candidate.is_file() else None)
    )
    if candidate is None:
        raise RuntimeError(f"SCANNER_NOT_AVAILABLE_{name.upper().replace('-', '_')}")
    return candidate


def _run(
    command: Sequence[str], cwd: Path, env_overrides: dict[str, str] | None = None
) -> int:
    environment = os.environ.copy()
    environment.update(env_overrides or {})
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
    )
    return completed.returncode


def _json_document(path: Path) -> object:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _wait_json_document(path: Path) -> object:
    for _ in range(20):
        document = _json_document(path)
        if document is not None:
            return document
        time.sleep(0.05)
    return None


def _pip_audit(temp_dir: Path, repo_root: Path) -> CanaryResult:
    requirement = temp_dir / "requirements.txt"
    output = temp_dir / "pip-audit.json"
    requirement.write_text("urllib3==1.25.2\n", encoding="utf-8")
    cache_dir = repo_root / ".local" / "cache" / "pip-audit"
    cache_dir.mkdir(parents=True, exist_ok=True)
    status = _run(
        (
            _executable("pip-audit"),
            "--strict",
            "--cache-dir",
            str(cache_dir),
            "--requirement",
            str(requirement),
            "--format",
            "json",
            "--output",
            str(output),
        ),
        temp_dir,
    )
    document = _json_document(output)
    dependencies = document.get("dependencies", []) if isinstance(document, dict) else []
    count = sum(
        len(item.get("vulns", []))
        for item in dependencies
        if isinstance(item, dict) and isinstance(item.get("vulns", []), list)
    )
    return CanaryResult(status, count)


def _bandit(temp_dir: Path) -> CanaryResult:
    source = temp_dir / "bandit_canary.py"
    output = temp_dir / "bandit.json"
    source.write_text(
        "import subprocess\nsubprocess.run(input(), shell=True, check=False)\n",
        encoding="utf-8",
    )
    status = _run(
        (
            _executable("bandit"),
            "-q",
            "-lll",
            "-f",
            "json",
            "-o",
            str(output),
            str(source),
        ),
        temp_dir,
    )
    document = _json_document(output)
    results = document.get("results", []) if isinstance(document, dict) else []
    return CanaryResult(status, len(results) if isinstance(results, list) else 0)


def _opengrep(temp_dir: Path, explicit: str | None, repo_root: Path) -> CanaryResult:
    source = temp_dir / "opengrep_canary.py"
    output = temp_dir / "opengrep.json"
    source.write_text("user_value = input()\neval(user_value)\n", encoding="utf-8")
    status = _run(
        (
            _executable("opengrep", explicit),
            "scan",
            "--config",
            str(repo_root / ".semgrep" / "security.yml"),
            "--disable-version-check",
            "--oss-only",
            "--strict",
            "--error",
            "--severity",
            "ERROR",
            "--json",
            "--output",
            str(output),
            str(source),
        ),
        temp_dir,
        {
            "LOCALAPPDATA": str(repo_root / ".local" / "data" / "opengrep"),
            "OPENGREP_ENABLE_VERSION_CHECK": "0",
            "SEMGREP_LOG_FILE": str(
                repo_root / ".local" / "data" / "opengrep" / "opengrep.log"
            ),
            "TMPDIR": str(repo_root / ".local" / "tmp"),
            "XDG_CACHE_HOME": str(repo_root / ".local" / "cache"),
        },
    )
    document = _wait_json_document(output)
    results = document.get("results", []) if isinstance(document, dict) else []
    return CanaryResult(status, len(results) if isinstance(results, list) else 0)


def _trivy(temp_dir: Path, explicit: str | None, repo_root: Path) -> CanaryResult:
    lockfile = {
        "name": "camera-ai-trivy-canary",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "requires": True,
        "packages": {
            "": {"name": "camera-ai-trivy-canary", "version": "1.0.0"},
            "node_modules/lodash": {"version": "4.17.20"},
        },
        "dependencies": {"lodash": {"version": "4.17.20"}},
    }
    (temp_dir / "package-lock.json").write_text(json.dumps(lockfile), encoding="utf-8")
    output = temp_dir / "trivy.json"
    cache_dir = Path(
        os.environ.get("TRIVY_CACHE_DIR", str(repo_root / ".local" / "cache" / "trivy"))
    ).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    status = _run(
        (
            _executable("trivy", explicit),
            "--cache-dir",
            str(cache_dir),
            "--db-repository",
            "ghcr.io/aquasecurity/trivy-db:2",
            "fs",
            "--scanners",
            "vuln",
            "--severity",
            "HIGH,CRITICAL",
            "--exit-code",
            "1",
            "--no-progress",
            "--skip-check-update",
            "--offline-scan",
            "--disable-telemetry",
            "--skip-version-check",
            "--format",
            "json",
            "--output",
            str(output),
            str(temp_dir),
        ),
        temp_dir,
    )
    document = _json_document(output)
    results = document.get("Results", []) if isinstance(document, dict) else []
    count = 0
    for result in results:
        if not isinstance(result, dict):
            continue
        for key in ("Vulnerabilities", "Misconfigurations"):
            findings = result.get(key, [])
            if isinstance(findings, list):
                count += len(findings)
    return CanaryResult(status, count)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scanner", choices=("all", *SCANNERS), nargs="?", default="all")
    parser.add_argument("--trivy", help="Explicit path to the pinned Trivy executable")
    parser.add_argument("--opengrep", help="Explicit path to the pinned OpenGrep executable")
    return parser.parse_args(argv)


def _run_scanner(
    scanner: str,
    temp_dir: Path,
    repo_root: Path,
    trivy_path: str | None,
    opengrep_path: str | None,
) -> CanaryResult:
    if scanner == "pip-audit":
        return _pip_audit(temp_dir, repo_root)
    if scanner == "bandit":
        return _bandit(temp_dir)
    if scanner == "opengrep":
        return _opengrep(temp_dir, opengrep_path, repo_root)
    return _trivy(temp_dir, trivy_path, repo_root)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    temp_root = repo_root / ".local" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    selected = SCANNERS if args.scanner == "all" else (args.scanner,)

    for scanner in selected:
        with tempfile.TemporaryDirectory(
            prefix=f"security-{scanner}-canary-", dir=temp_root
        ) as directory:
            temp_dir = Path(directory)
            try:
                result = _run_scanner(
                    scanner, temp_dir, repo_root, args.trivy, args.opengrep
                )
            except RuntimeError as exc:
                print(f"scanner_canary=FAIL scanner={scanner} code={exc}")
                return 1
        if result.status != 1 or result.finding_count < 1:
            print(
                f"scanner_canary=FAIL scanner={scanner} "
                f"status={result.status} synthetic_findings={result.finding_count}"
            )
            return 1
        print(
            f"scanner_canary=PASS scanner={scanner} "
            f"synthetic_findings={result.finding_count} output_discarded=true"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
