from __future__ import annotations

from dataclasses import fields, replace

import pytest
from ansvis_adapter.application.telemetry import EvaluateOperationalAlerts, NullMetricsSink
from ansvis_adapter.domain.ingestion import AlertSeverity, EventOperationalSnapshot


def snapshot(**overrides: int) -> EventOperationalSnapshot:
    values = {
        "accepted_receipts": 10,
        "pending_messages": 1,
        "published_messages": 9,
        "failed_messages": 0,
        "retryable_attempts": 2,
        "quarantined_conflicts": 1,
        "delayed_messages": 0,
        "oldest_pending_seconds": 0,
    }
    values.update(overrides)
    return EventOperationalSnapshot(**values)


def test_operational_snapshot_has_only_bounded_aggregate_fields() -> None:
    field_names = {field.name for field in fields(EventOperationalSnapshot)}
    assert field_names == {
        "accepted_receipts",
        "pending_messages",
        "published_messages",
        "failed_messages",
        "retryable_attempts",
        "quarantined_conflicts",
        "delayed_messages",
        "oldest_pending_seconds",
    }
    assert all(
        marker not in name
        for name in field_names
        for marker in ("actor", "camera", "event_id", "evidence", "person", "school", "subject")
    )
    with pytest.raises(ValueError, match="non-negative"):
        replace(snapshot(), accepted_receipts=-1)
    with pytest.raises(ValueError, match="cannot exceed"):
        replace(snapshot(), delayed_messages=2)


@pytest.mark.parametrize(
    ("oldest_seconds", "expected_severity"),
    [
        (60, None),
        (61, AlertSeverity.WARNING),
        (600, AlertSeverity.WARNING),
        (601, AlertSeverity.CRITICAL),
    ],
)
def test_oldest_message_alert_matches_the_approved_thresholds(
    oldest_seconds: int, expected_severity: AlertSeverity | None
) -> None:
    alerts = EvaluateOperationalAlerts().execute(
        snapshot(
            oldest_pending_seconds=oldest_seconds,
            delayed_messages=0 if oldest_seconds <= 60 else 1,
        )
    )
    if expected_severity is None:
        assert alerts == ()
    else:
        assert len(alerts) == 1
        assert alerts[0].code == "EVENT_OUTBOX_OLDEST_MESSAGE"
        assert alerts[0].severity is expected_severity


def test_any_untriaged_event_dlq_message_is_an_immediate_warning() -> None:
    alerts = EvaluateOperationalAlerts().execute(snapshot(failed_messages=1))
    assert [(alert.code, alert.severity) for alert in alerts] == [
        ("EVENT_OUTBOX_DLQ_UNTRIAGED", AlertSeverity.WARNING)
    ]


def test_point_in_time_backlog_only_fires_the_immediate_critical_boundary() -> None:
    evaluator = EvaluateOperationalAlerts()
    assert evaluator.execute(snapshot(pending_messages=20_000)) == ()
    alerts = evaluator.execute(snapshot(pending_messages=20_001))
    assert [(alert.code, alert.severity) for alert in alerts] == [
        ("EVENT_OUTBOX_BACKLOG", AlertSeverity.CRITICAL)
    ]


def test_null_metrics_sink_accepts_only_the_named_metric_vocabulary() -> None:
    metrics = NullMetricsSink()
    for metric, outcome in (
        ("event_ingestion_total", "accepted"),
        ("event_ingestion_total", "duplicate"),
        ("event_ingestion_total", "rejected"),
        ("event_ingestion_total", "conflict"),
        ("event_ingestion_rejections_total", "rate_limited"),
        ("event_ingestion_rejections_total", "rate_limit_unavailable"),
        ("event_outbox_dispatch_total", "retry_scheduled"),
        ("event_outbox_dispatch_total", "dead_lettered"),
        ("event_outbox_replay_total", "replayed"),
    ):
        metrics.increment(metric, outcome=outcome)
    with pytest.raises(ValueError, match="allowlisted"):
        metrics.increment("event_ingestion_total", outcome="camera_test_0001")
