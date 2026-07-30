"""Validate queue thresholds, metric references, and retry constants without runtime data."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, cast


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("queue policy object expected")
    return cast(dict[str, Any], value)


def _int_constant(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        target_name: str | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            target_name = target.id if isinstance(target, ast.Name) else None
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target_name = node.target.id if isinstance(node.target, ast.Name) else None
            value = node.value
        if target_name == name and isinstance(value, ast.Constant) and isinstance(value.value, int):
            return value.value
    raise ValueError(f"integer constant missing: {path.name}/{name}")


def run_checks() -> list[str]:
    failures: list[str] = []
    try:
        from camera_ai_metrics import REGISTRY, load_queue_policy, retry_policy_drift
    except Exception as error:  # pragma: no cover - import failure is the finding
        return [f"queue policy import failed: {type(error).__name__}"]

    repo_root = Path(__file__).resolve().parents[1]
    event_policy = (
        repo_root
        / "services"
        / "ansvis-adapter"
        / "src"
        / "ansvis_adapter"
        / "application"
        / "outbox.py"
    )
    notification_policy = (
        repo_root
        / "services"
        / "notification-service"
        / "src"
        / "notification_service"
        / "domain"
        / "policies.py"
    )
    event_attempts = _int_constant(event_policy, "MAX_ATTEMPTS")
    event_base = _int_constant(event_policy, "BASE_BACKOFF_SECONDS")
    notification_attempts = _int_constant(notification_policy, "MAX_ATTEMPTS")
    notification_base = _int_constant(notification_policy, "BASE_BACKOFF_SECONDS")

    policy = load_queue_policy()
    queues = _object(policy["queues"])
    contracts = _object(policy["retry_contracts"])
    for queue_code, raw_queue in queues.items():
        queue = _object(raw_queue)
        for field in (
            "depth_metric",
            "dispatch_metric",
            "dlq_metric",
            "drain_eta_metric",
            "oldest_metric",
        ):
            if queue.get(field) not in REGISTRY:
                failures.append(f"unregistered metric: {queue_code}/{field}")

    observed = {
        "event_outbox": (event_attempts, event_base),
        "audit_outbox": (event_attempts, event_base),
        "notification": (notification_attempts, notification_base),
    }
    for queue_code, (attempts, base) in observed.items():
        contract = _object(contracts[queue_code])
        if attempts != contract.get("observed_max_attempts"):
            failures.append(f"retry attempt drift: {queue_code}")
        if base != contract.get("observed_base_backoff_seconds"):
            failures.append(f"retry base drift: {queue_code}")

    approved_exceptions = {
        queue_code
        for queue_code, raw_contract in contracts.items()
        if _object(raw_contract).get("status") == "approved_versioned_exception"
    }
    if set(retry_policy_drift()) != approved_exceptions:
        failures.append("retry target drift does not match approved versioned exceptions")
    return failures


def main() -> int:
    failures = run_checks()
    if failures:
        for failure in failures:
            print(f"queue_policy=FAIL {failure}")
        return 1
    from camera_ai_metrics import POLICY_VERSION, load_queue_policy, retry_policy_drift

    queues = _object(load_queue_policy()["queues"])
    print("queue_policy=PASS")
    print(f"policy_version={POLICY_VERSION}")
    print(f"queues_checked={len(queues)}")
    print("runtime_activation=INACTIVE")
    print(f"approved_retry_exceptions={len(retry_policy_drift())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
