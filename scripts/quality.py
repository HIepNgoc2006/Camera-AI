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
        "lint": (
            (python, "-m", "ruff", "check", "scripts"),
            (python, "-m", "ruff", "format", "--check", "scripts"),
        ),
        "typecheck": ((python, "-m", "mypy", "scripts"),),
        "unit": ((python, "-m", "pytest", "-q", "scripts/tests"),),
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
