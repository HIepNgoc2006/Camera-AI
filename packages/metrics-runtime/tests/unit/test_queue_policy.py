from __future__ import annotations

from dataclasses import fields

import pytest
from camera_ai_metrics import (
    REGISTRY,
    AlertSeverity,
    CircuitState,
    QueuePolicyEvaluator,
    QueueSnapshot,
    load_queue_policy,
    retry_policy_drift,
)
from camera_ai_metrics.queue_policy import ClaimMode


def snapshot(**overrides: object) -> QueueSnapshot:
    values: dict[str, object] = {"queue_code": "event_outbox"}
    values.update(overrides)
    return QueueSnapshot(**values)  # type: ignore[arg-type]


def test_policy_table_covers_every_queue_with_registered_metrics() -> None:
    policy = load_queue_policy()
    queues = policy["queues"]
    assert isinstance(queues, dict)
    assert set(queues) == {"audit_outbox", "event_outbox", "notification", "report_export"}
    for queue in queues.values():
        assert isinstance(queue, dict)
        for field in (
            "depth_metric",
            "drain_eta_metric",
            "oldest_metric",
            "dlq_metric",
            "dispatch_metric",
        ):
            assert queue[field] in REGISTRY


def test_snapshot_contains_only_bounded_aggregate_fields() -> None:
    names = {field.name for field in fields(QueueSnapshot)}
    assert names == {
        "queue_code",
        "depth_messages",
        "depth_breach_seconds",
        "drain_eta_seconds",
        "dlq_arrivals_10m",
        "oldest_unpublished_seconds",
        "downstream_attempts_1m",
        "downstream_errors_1m",
    }
    assert all(
        marker not in name
        for name in names
        for marker in ("camera", "endpoint", "event_id", "payload", "person", "school", "subject")
    )
    with pytest.raises(ValueError, match="non-negative"):
        snapshot(depth_messages=-1)


@pytest.mark.parametrize(
    ("queue_snapshot", "expected_code", "expected_severity"),
    [
        (snapshot(depth_messages=5001, depth_breach_seconds=300), "QUEUE_DEPTH", "warning"),
        (snapshot(depth_messages=20001), "QUEUE_DEPTH", "critical"),
        (snapshot(drain_eta_seconds=901), "QUEUE_DEPTH", "critical"),
        (snapshot(dlq_arrivals_10m=1), "QUEUE_DLQ", "warning"),
        (snapshot(dlq_arrivals_10m=31), "QUEUE_DLQ", "critical"),
        (
            snapshot(oldest_unpublished_seconds=61),
            "QUEUE_OLDEST_UNPUBLISHED",
            "warning",
        ),
        (
            snapshot(oldest_unpublished_seconds=601),
            "QUEUE_OLDEST_UNPUBLISHED",
            "critical",
        ),
        (
            snapshot(downstream_attempts_1m=100, downstream_errors_1m=11),
            "QUEUE_DOWNSTREAM_CIRCUIT",
            "critical",
        ),
    ],
)
def test_each_exact_threshold_fires(
    queue_snapshot: QueueSnapshot, expected_code: str, expected_severity: str
) -> None:
    evaluator = QueuePolicyEvaluator()
    alerts = evaluator.evaluate(queue_snapshot)
    assert [(alert.alert_code, alert.severity.value) for alert in alerts] == [
        (expected_code, expected_severity)
    ]
    cleared = evaluator.lifecycle(
        alerts,
        snapshot(queue_code=queue_snapshot.queue_code),
    )
    assert cleared.active == ()
    assert cleared.cleared == alerts


def test_warning_critical_and_clear_lifecycle() -> None:
    evaluator = QueuePolicyEvaluator()
    warning = evaluator.lifecycle(
        (),
        snapshot(depth_messages=5001, depth_breach_seconds=300),
    )
    assert warning.fired[0].severity is AlertSeverity.WARNING
    critical = evaluator.lifecycle(warning.active, snapshot(drain_eta_seconds=901))
    assert critical.fired[0].severity is AlertSeverity.CRITICAL
    clear = evaluator.lifecycle(critical.active, snapshot())
    assert clear.active == ()
    assert [(item.alert_code, item.severity) for item in clear.cleared] == [
        ("QUEUE_DEPTH", AlertSeverity.CRITICAL)
    ]


def test_audit_dlq_is_critical_on_first_arrival() -> None:
    alerts = QueuePolicyEvaluator().evaluate(
        snapshot(queue_code="audit_outbox", dlq_arrivals_10m=1)
    )
    assert alerts[0].alert_code == "QUEUE_DLQ"
    assert alerts[0].severity is AlertSeverity.CRITICAL


def test_exact_dlq_rate_boundary_remains_warning_until_exceeded() -> None:
    evaluator = QueuePolicyEvaluator()
    at_boundary = evaluator.evaluate(snapshot(dlq_arrivals_10m=30))
    above_boundary = evaluator.evaluate(snapshot(dlq_arrivals_10m=31))
    assert at_boundary[0].severity is AlertSeverity.WARNING
    assert above_boundary[0].severity is AlertSeverity.CRITICAL


def test_circuit_stops_claims_then_probes_and_closes() -> None:
    evaluator = QueuePolicyEvaluator()
    unhealthy = snapshot(downstream_attempts_1m=100, downstream_errors_1m=11)
    opened = evaluator.circuit(unhealthy, current=CircuitState.CLOSED)
    assert (opened.state, opened.claim_mode) == (CircuitState.OPEN, ClaimMode.STOP)
    half_open = evaluator.circuit(snapshot(), current=opened.state, open_seconds=60)
    assert (half_open.state, half_open.claim_mode) == (
        CircuitState.HALF_OPEN,
        ClaimMode.PROBE,
    )
    closed = evaluator.circuit(
        snapshot(downstream_attempts_1m=3),
        current=half_open.state,
        half_open_successes=3,
    )
    assert (closed.state, closed.claim_mode) == (CircuitState.CLOSED, ClaimMode.NORMAL)


def test_approved_retry_contract_exceptions_remain_explicit() -> None:
    assert retry_policy_drift() == ("audit_outbox", "event_outbox")
