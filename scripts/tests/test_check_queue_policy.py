from __future__ import annotations

from scripts.check_queue_policy import run_checks


def test_queue_policy_checker_passes_with_approved_versioned_exceptions() -> None:
    assert run_checks() == []
