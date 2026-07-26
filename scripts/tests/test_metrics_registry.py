"""The metrics-registry checker passes on the committed registry and fails on drift."""

from __future__ import annotations

from scripts.check_metrics_registry import BASELINE_METRICS, main, run_checks


def test_checker_passes_on_the_committed_registry(capsys) -> None:  # type: ignore[no-untyped-def]
    assert run_checks() == []
    assert main() == 0
    output = capsys.readouterr().out
    assert "metrics_registry=PASS" in output
    assert "policy_version=metrics_registry_v1" in output


def test_baseline_list_matches_the_registry_exactly() -> None:
    from camera_ai_metrics import REGISTRY

    assert set(BASELINE_METRICS) == set(REGISTRY)
