from __future__ import annotations

import sys
from pathlib import Path

from scripts.quality import quality_commands, run_commands, selected_commands

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_all_expands_each_supported_gate_in_order() -> None:
    commands = quality_commands("python")

    assert selected_commands("all", "python") == (
        *commands["repository"],
        *commands["foundation"],
        *commands["compose"],
        *commands["fixtures"],
        *commands["time-policy"],
        *commands["evidence-access-policy"],
        *commands["notification-privacy-policy"],
        *commands["ansvis-contract"],
        *commands["lint"],
        *commands["typecheck"],
        *commands["unit"],
    )


def test_runner_propagates_a_failing_command_status() -> None:
    fake_failure = (sys.executable, "-c", "raise SystemExit(7)")

    assert run_commands((fake_failure,), REPO_ROOT) == 7
