"""Registry invariants: bounded vocabulary, kind conventions, baseline presence."""

from __future__ import annotations

import pytest
from camera_ai_metrics import (
    MAX_LABEL_CARDINALITY,
    REGISTRY,
    MetricKind,
    MetricSpec,
    spec_for,
    validate_counter,
    validate_gauge,
    validate_observation,
)

BASELINE_NAMES = {
    "event_ingestion_rejections_total",
    "event_ingestion_total",
    "event_outbox_dispatch_total",
    "event_outbox_replay_total",
    "event_operational_alerts_total",
    "event_ingestion_ack_seconds",
    "event_outbox_enqueue_to_publish_seconds",
    "event_outbox_backlog_messages",
    "event_outbox_drain_eta_seconds",
    "event_outbox_oldest_pending_seconds",
    "event_audit_outbox_backlog_messages",
    "event_audit_outbox_drain_eta_seconds",
    "event_audit_outbox_oldest_pending_seconds",
    "notification_dispatch_total",
    "notification_dlq_arrivals_total",
    "notification_reauthorization_seconds",
    "notification_retry_backlog_messages",
    "notification_drain_eta_seconds",
    "notification_oldest_pending_seconds",
    "report_query_total",
    "report_export_total",
    "report_export_queue_depth_messages",
    "report_export_drain_eta_seconds",
    "report_export_oldest_pending_seconds",
    "report_export_dlq_arrivals_total",
}


def test_baseline_metrics_are_registered() -> None:
    assert set(REGISTRY) >= BASELINE_NAMES


def test_every_spec_respects_cardinality_and_kind_conventions() -> None:
    for spec in REGISTRY.values():
        assert len(spec.outcomes) <= MAX_LABEL_CARDINALITY
        if spec.kind is MetricKind.COUNTER:
            assert spec.name.endswith("_total")
            assert spec.outcomes
        elif spec.kind is MetricKind.HISTOGRAM:
            assert spec.name.endswith("_seconds")
            assert list(spec.buckets) == sorted(set(spec.buckets))
        else:
            assert spec.name.endswith(("_seconds", "_messages"))
            assert not spec.outcomes


def test_registry_is_immutable() -> None:
    with pytest.raises(TypeError):
        REGISTRY["event_injected_total"] = spec_for("event_ingestion_total")  # type: ignore[index]


def test_unregistered_and_mismatched_emissions_fail() -> None:
    with pytest.raises(ValueError, match="not registered"):
        spec_for("event_unregistered_total")
    with pytest.raises(ValueError, match="not allowlisted"):
        validate_counter("event_ingestion_total", "surprise_outcome")
    with pytest.raises(ValueError, match="not a registered histogram"):
        validate_observation("event_ingestion_total")
    with pytest.raises(ValueError, match="not a registered gauge"):
        validate_gauge("event_ingestion_ack_seconds")


@pytest.mark.parametrize(
    ("name", "kind", "outcomes", "buckets", "match"),
    [
        ("Bad-Name_total", MetricKind.COUNTER, ("ok",), (), "snake_case"),
        ("event_thing_seconds", MetricKind.COUNTER, ("ok",), (), "suffix"),
        ("event_thing_total", MetricKind.COUNTER, (), (), "bounded and non-empty"),
        (
            "event_thing_total",
            MetricKind.COUNTER,
            tuple(f"value_{i}" for i in range(MAX_LABEL_CARDINALITY + 1)),
            (),
            "bounded and non-empty",
        ),
        ("event_thing_total", MetricKind.COUNTER, ("dup", "dup"), (), "unique"),
        ("event_thing_seconds", MetricKind.HISTOGRAM, (), (1.0, 0.5, 2.0), "ascending"),
        ("event_thing_seconds", MetricKind.HISTOGRAM, ("no",), (0.1, 0.5, 1.0), "outcome label"),
        ("event_thing_messages", MetricKind.GAUGE, (), (1.0, 2.0, 3.0), "buckets"),
        ("event_thing_total", MetricKind.COUNTER, ("ok",), (1.0, 2.0, 3.0), "buckets"),
    ],
)
def test_spec_construction_fails_closed(
    name: str,
    kind: MetricKind,
    outcomes: tuple[str, ...],
    buckets: tuple[float, ...],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        MetricSpec(name=name, kind=kind, help_text="synthetic", outcomes=outcomes, buckets=buckets)
