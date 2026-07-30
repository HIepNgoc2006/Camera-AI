"""Run the repository's documented quality gates with stable exit codes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

Command = tuple[str, ...]


def quality_commands(python: str) -> dict[str, tuple[Command, ...]]:
    """Return commands for scopes that exist in the repository today."""

    return {
        "repository": ((python, "scripts/check_repository_safety.py"),),
        "foundation": ((python, "scripts/check_foundation_safety.py"),),
        "compose": ((python, "scripts/check_compose_safety.py"),),
        "fixtures": (
            (python, "scripts/check_fixture_safety.py"),
            (python, "-m", "scripts.test_fixture_safety_canary"),
        ),
        "time-policy": ((python, "scripts/check_time_policy.py"),),
        "ai-shadow-review-policy": ((python, "scripts/check_ai_shadow_review_policy.py"),),
        "evidence-access-policy": ((python, "scripts/check_evidence_access_policy.py"),),
        "notification-privacy-policy": ((python, "scripts/check_notification_privacy_policy.py"),),
        "consent-withdrawal-policy": ((python, "scripts/check_consent_withdrawal_policy.py"),),
        "authorization-catalog": ((python, "scripts/check_authorization_catalog.py"),),
        "api-contract": ((python, "scripts/check_api_contract.py"),),
        "ansvis-contract": ((python, "-m", "scripts.check_ansvis_event_contract"),),
        "metrics-registry": ((python, "scripts/check_metrics_registry.py"),),
        "queue-policy": ((python, "scripts/check_queue_policy.py"),),
        "lint": (
            (python, "-m", "ruff", "check", "scripts", "services", "packages", "workers"),
            (
                python,
                "-m",
                "ruff",
                "format",
                "--check",
                "scripts",
                "services",
                "packages",
                "workers",
            ),
        ),
        "typecheck": (
            (python, "-m", "mypy", "scripts"),
            (
                python,
                "-m",
                "mypy",
                "packages/audit-producer/src",
                "packages/audit-producer/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "packages/authorization-runtime/src",
                "packages/authorization-runtime/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "packages/crypto-runtime/src",
                "packages/crypto-runtime/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "packages/metrics-runtime/src",
                "packages/metrics-runtime/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/api-gateway/src",
                "services/api-gateway/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/identity-service/src",
                "services/identity-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/school-service/src",
                "services/school-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/audit-log-service/src",
                "services/audit-log-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/consent-service/src",
                "services/consent-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/camera-registry-service/src",
                "services/camera-registry-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/ansvis-adapter/src",
                "services/ansvis-adapter/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/attendance-service/src",
                "services/attendance-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/timekeeping-service/src",
                "services/timekeeping-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/notification-service/src",
                "services/notification-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/evidence-service/src",
                "services/evidence-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "services/report-service/src",
                "services/report-service/tests",
            ),
            (
                python,
                "-m",
                "mypy",
                "workers/event-outbox-worker/src",
                "workers/event-outbox-worker/tests",
            ),
        ),
        "unit": (
            (
                python,
                "-m",
                "pytest",
                "-q",
                "scripts/tests",
                "packages/audit-producer/tests",
                "packages/authorization-runtime/tests",
                "packages/crypto-runtime/tests",
                "packages/metrics-runtime/tests",
                "services/api-gateway/tests",
                "services/identity-service/tests",
                "services/school-service/tests",
                "services/audit-log-service/tests",
                "services/consent-service/tests",
                "services/camera-registry-service/tests",
                "services/ansvis-adapter/tests",
                "services/attendance-service/tests",
                "services/timekeeping-service/tests",
                "services/notification-service/tests",
                "services/evidence-service/tests",
                "services/report-service/tests",
                "workers/event-outbox-worker/tests",
            ),
        ),
    }


def run_commands(commands: Sequence[Command], repo_root: Path) -> int:
    """Run commands in order and return the first non-zero status."""

    for command in commands:
        completed = subprocess.run(command, cwd=repo_root, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


def selected_commands(gate: str, python: str) -> tuple[Command, ...]:
    """Expand a named gate without claiming unscaffolded platform checks."""

    commands = quality_commands(python)
    if gate == "all":
        return tuple(
            command
            for name in (
                "repository",
                "foundation",
                "compose",
                "fixtures",
                "time-policy",
                "ai-shadow-review-policy",
                "evidence-access-policy",
                "notification-privacy-policy",
                "consent-withdrawal-policy",
                "authorization-catalog",
                "api-contract",
                "ansvis-contract",
                "metrics-registry",
                "queue-policy",
                "lint",
                "typecheck",
                "unit",
            )
            for command in commands[name]
        )
    return commands[gate]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "gate",
        choices=(
            "all",
            "repository",
            "foundation",
            "compose",
            "fixtures",
            "time-policy",
            "ai-shadow-review-policy",
            "evidence-access-policy",
            "notification-privacy-policy",
            "consent-withdrawal-policy",
            "authorization-catalog",
            "api-contract",
            "ansvis-contract",
            "metrics-registry",
            "queue-policy",
            "lint",
            "typecheck",
            "unit",
        ),
        help="quality gate to run",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    return run_commands(selected_commands(args.gate, sys.executable), repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
