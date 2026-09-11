from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from scripts.quality import quality_commands, run_commands, selected_commands

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_all_expands_each_supported_gate_in_order() -> None:
    commands = quality_commands("python")

    assert selected_commands("all", "python") == (
        *commands["repository"],
        *commands["security-scanning-policy"],
        *commands["foundation"],
        *commands["compose"],
        *commands["fixtures"],
        *commands["time-policy"],
        *commands["ai-shadow-review-policy"],
        *commands["evidence-access-policy"],
        *commands["notification-privacy-policy"],
        *commands["consent-withdrawal-policy"],
        *commands["authorization-catalog"],
        *commands["api-contract"],
        *commands["ansvis-contract"],
        *commands["metrics-registry"],
        *commands["queue-policy"],
        *commands["abuse-protection-policy"],
        *commands["web-bff-session-policy"],
        *commands["web"],
        *commands["lint"],
        *commands["typecheck"],
        *commands["unit"],
    )


def test_runner_propagates_a_failing_command_status() -> None:
    fake_failure = (sys.executable, "-c", "raise SystemExit(7)")

    assert run_commands((fake_failure,), REPO_ROOT) == 7


def test_direct_discovery_covers_quality_runner_services() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    commands = quality_commands("python")
    unit_service_test_targets = {
        argument
        for command in commands["unit"]
        for argument in command
        if argument.startswith("services/") and argument.endswith("/tests")
    }
    mypy_service_source_targets = {
        argument
        for command in commands["typecheck"]
        for argument in command
        if argument.startswith("services/") and argument.endswith("/src")
    }

    pytest_config = config["tool"]["pytest"]["ini_options"]
    mypy_config = config["tool"]["mypy"]
    pytest_service_testpaths = {
        target
        for target in pytest_config["testpaths"]
        if target.startswith("services/") and target.endswith("/tests")
    }
    pytest_service_pythonpath = {
        target
        for target in pytest_config["pythonpath"]
        if target.startswith("services/") and target.endswith("/src")
    }
    configured_mypy_service_sources = {
        target
        for target in mypy_config["files"]
        if target.startswith("services/") and target.endswith("/src")
    }
    configured_mypy_service_import_roots = {
        target
        for target in mypy_config["mypy_path"]
        if target.startswith("services/") and target.endswith("/src")
    }

    assert unit_service_test_targets == pytest_service_testpaths
    assert mypy_service_source_targets == pytest_service_pythonpath
    assert mypy_service_source_targets == configured_mypy_service_sources
    assert mypy_service_source_targets == configured_mypy_service_import_roots

    for service in ("attendance-service", "report-service"):
        source_target = f"services/{service}/src"
        test_target = f"services/{service}/tests"

        assert source_target in mypy_service_source_targets
        assert source_target in pytest_service_pythonpath
        assert source_target in configured_mypy_service_sources
        assert source_target in configured_mypy_service_import_roots
        assert test_target in unit_service_test_targets
        assert test_target in pytest_service_testpaths
