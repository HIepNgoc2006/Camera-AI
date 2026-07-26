"""Prometheus sink behaviour and the loopback-only scrape server."""

from __future__ import annotations

from urllib.request import urlopen

import pytest
from camera_ai_metrics import PrometheusMetricsSink, start_internal_metrics_server


def test_registered_emissions_appear_in_exposition_with_correct_types() -> None:
    sink = PrometheusMetricsSink()

    sink.increment("event_outbox_dispatch_total", outcome="published")
    sink.increment("event_outbox_dispatch_total", outcome="published")
    sink.observe("event_ingestion_ack_seconds", seconds=0.123)
    sink.set_gauge("event_outbox_backlog_messages", value=7)

    exposition = sink.scrape().decode()
    assert 'event_outbox_dispatch_total{outcome="published"} 2.0' in exposition
    assert "# TYPE event_outbox_dispatch_total counter" in exposition
    assert "# TYPE event_ingestion_ack_seconds histogram" in exposition
    assert "event_ingestion_ack_seconds_count 1.0" in exposition
    assert "# TYPE event_outbox_backlog_messages gauge" in exposition
    assert "event_outbox_backlog_messages 7.0" in exposition


def test_unregistered_or_mismatched_emissions_raise() -> None:
    sink = PrometheusMetricsSink()

    with pytest.raises(ValueError):
        sink.increment("event_unregistered_total", outcome="published")
    with pytest.raises(ValueError):
        sink.increment("event_outbox_dispatch_total", outcome="tenant_test_0001")
    with pytest.raises(ValueError):
        sink.observe("event_outbox_dispatch_total", seconds=0.1)
    with pytest.raises(ValueError):
        sink.observe("event_ingestion_ack_seconds", seconds=-1.0)
    with pytest.raises(ValueError):
        sink.set_gauge("event_ingestion_ack_seconds", value=1.0)


def test_two_sinks_do_not_collide() -> None:
    first = PrometheusMetricsSink()
    second = PrometheusMetricsSink()

    first.increment("event_outbox_replay_total", outcome="replayed")

    assert b"event_outbox_replay_total" in first.scrape()
    assert 'event_outbox_replay_total{outcome="replayed"}' not in second.scrape().decode()


def test_internal_server_binds_loopback_and_serves_the_sink() -> None:
    sink = PrometheusMetricsSink()
    sink.increment("event_ingestion_total", outcome="accepted")
    server = start_internal_metrics_server(sink, port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
        with urlopen(f"http://127.0.0.1:{server.server_port}/metrics", timeout=5) as response:
            body = response.read().decode()
        assert 'event_ingestion_total{outcome="accepted"} 1.0' in body
    finally:
        server.shutdown()


def test_internal_server_rejects_non_loopback_addresses() -> None:
    sink = PrometheusMetricsSink()

    with pytest.raises(ValueError, match="loopback"):
        start_internal_metrics_server(sink, port=0, addr="0.0.0.0")
    with pytest.raises(ValueError, match="valid TCP port"):
        start_internal_metrics_server(sink, port=70_000)
