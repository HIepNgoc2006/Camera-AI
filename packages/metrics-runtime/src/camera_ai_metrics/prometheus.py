"""Registry-backed Prometheus sink and the internal-only scrape server.

The sink instantiates exactly the registered metrics up front; emitting anything outside the
registry raises `ValueError` (call sites are expected to swallow metric errors so telemetry can
never break a request or drain path). Each sink owns a fresh `CollectorRegistry`, so repeated
application factories in tests never collide.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from wsgiref.simple_server import WSGIServer

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    start_http_server,
)

from camera_ai_metrics.registry import (
    OUTCOME_LABEL,
    REGISTRY,
    MetricKind,
    validate_counter,
    validate_gauge,
    validate_observation,
)


@dataclass(slots=True)
class PrometheusMetricsSink:
    """Fail-loud, registry-validated implementation of the platform metric surface."""

    collector_registry: CollectorRegistry = field(default_factory=CollectorRegistry)
    _counters: dict[str, Counter] = field(default_factory=dict, init=False, repr=False)
    _histograms: dict[str, Histogram] = field(default_factory=dict, init=False, repr=False)
    _gauges: dict[str, Gauge] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for spec in REGISTRY.values():
            if spec.kind is MetricKind.COUNTER:
                self._counters[spec.name] = Counter(
                    spec.name,
                    spec.help_text,
                    labelnames=(OUTCOME_LABEL,),
                    registry=self.collector_registry,
                )
            elif spec.kind is MetricKind.HISTOGRAM:
                self._histograms[spec.name] = Histogram(
                    spec.name,
                    spec.help_text,
                    buckets=spec.buckets,
                    registry=self.collector_registry,
                )
            else:
                self._gauges[spec.name] = Gauge(
                    spec.name,
                    spec.help_text,
                    registry=self.collector_registry,
                )

    def increment(self, metric: str, *, outcome: str) -> None:
        validate_counter(metric, outcome)
        self._counters[metric].labels(outcome).inc()

    def observe(self, metric: str, *, seconds: float) -> None:
        validate_observation(metric)
        if seconds < 0:
            raise ValueError("observed duration must be non-negative")
        self._histograms[metric].observe(seconds)

    def set_gauge(self, metric: str, *, value: float) -> None:
        validate_gauge(metric)
        if value < 0:
            raise ValueError("gauge value must be non-negative")
        self._gauges[metric].set(value)

    def scrape(self) -> bytes:
        """Return the current exposition payload (used by tests and diagnostics)."""

        return generate_latest(self.collector_registry)


def start_internal_metrics_server(
    sink: PrometheusMetricsSink, *, port: int, addr: str = "127.0.0.1"
) -> WSGIServer:
    """Expose the sink on a loopback-only port; never route through the API gateway.

    Rejects any non-loopback bind address so a configuration mistake cannot publish metrics
    on an externally reachable interface. Returns the server so callers can read the bound
    port (`server.server_port`, useful with `port=0` in tests) and shut it down.
    """

    if not ipaddress.ip_address(addr).is_loopback:
        raise ValueError("internal metrics server must bind a loopback address")
    if not 0 <= port <= 65_535:
        raise ValueError("metrics port must be a valid TCP port")
    server, _thread = start_http_server(port, addr=addr, registry=sink.collector_registry)
    return server
