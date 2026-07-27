"""`metrics_registry_v1` — the single allowed metric/label vocabulary.

Every metric a Camera AI process may emit is declared here with its kind, help text, and — for
labelled counters — the complete closed set of allowed label values. Emitting an unregistered
metric name or label value fails validation; labels never carry tenant, camera, subject, event or
any other identifier, so cardinality is bounded by construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

REGISTRY_VERSION = "metrics_registry_v1"
MAX_LABEL_CARDINALITY = 8
OUTCOME_LABEL = "outcome"

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
_VALUE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class MetricKind(StrEnum):
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"


_KIND_SUFFIXES: dict[MetricKind, tuple[str, ...]] = {
    MetricKind.COUNTER: ("_total",),
    MetricKind.HISTOGRAM: ("_seconds",),
    MetricKind.GAUGE: ("_seconds", "_messages"),
}


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One registered metric; immutable and structurally validated."""

    name: str
    kind: MetricKind
    help_text: str
    outcomes: tuple[str, ...] = ()
    buckets: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if _NAME_PATTERN.fullmatch(self.name) is None:
            raise ValueError("metric name must be bounded snake_case")
        if not self.name.endswith(_KIND_SUFFIXES[self.kind]):
            raise ValueError("metric name suffix must match its kind convention")
        if not self.help_text.strip():
            raise ValueError("metric help text is required")
        if self.kind is MetricKind.COUNTER:
            if not 1 <= len(self.outcomes) <= MAX_LABEL_CARDINALITY:
                raise ValueError("counter outcome vocabulary must be bounded and non-empty")
            if len(set(self.outcomes)) != len(self.outcomes) or any(
                _VALUE_PATTERN.fullmatch(value) is None for value in self.outcomes
            ):
                raise ValueError("counter outcomes must be unique bounded snake_case values")
            if self.buckets:
                raise ValueError("counters do not declare buckets")
        else:
            if self.outcomes:
                raise ValueError("only counters carry the outcome label")
            if self.kind is MetricKind.HISTOGRAM:
                if len(self.buckets) < 3 or list(self.buckets) != sorted(set(self.buckets)):
                    raise ValueError("histogram buckets must be ascending and unique")
            elif self.buckets:
                raise ValueError("gauges do not declare buckets")


_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        name="event_ingestion_total",
        kind=MetricKind.COUNTER,
        help_text="ANSVIS ingestion requests by bounded outcome.",
        outcomes=("accepted", "conflict", "duplicate", "rejected"),
    ),
    MetricSpec(
        name="event_outbox_dispatch_total",
        kind=MetricKind.COUNTER,
        help_text="Outbox dispatch attempts by bounded outcome.",
        outcomes=("dead_lettered", "empty", "published", "refused", "retry_scheduled"),
    ),
    MetricSpec(
        name="event_consent_gate_total",
        kind=MetricKind.COUNTER,
        help_text="Consent gate decisions on biometric event ingestion by bounded outcome.",
        outcomes=("allowed", "blocked", "not_required", "unavailable"),
    ),
    MetricSpec(
        name="event_outbox_replay_total",
        kind=MetricKind.COUNTER,
        help_text="Operator-authorized outbox replays.",
        outcomes=("replayed",),
    ),
    MetricSpec(
        name="event_operational_alerts_total",
        kind=MetricKind.COUNTER,
        help_text="Approved operational alert evaluations that fired.",
        outcomes=("event_outbox_dlq_untriaged", "event_outbox_oldest_message"),
    ),
    MetricSpec(
        name="event_audit_delivery_total",
        kind=MetricKind.COUNTER,
        help_text="Audit-intent delivery attempts by bounded outcome.",
        outcomes=("dead_lettered", "delivered", "duplicate", "empty", "retry_scheduled"),
    ),
    MetricSpec(
        name="event_ingestion_ack_seconds",
        kind=MetricKind.HISTOGRAM,
        help_text="Ingestion request handling time to acknowledgement.",
        buckets=(0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0),
    ),
    MetricSpec(
        name="event_outbox_enqueue_to_publish_seconds",
        kind=MetricKind.HISTOGRAM,
        help_text="Delay from outbox record time to confirmed publish.",
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 15.0, 60.0, 300.0, 900.0),
    ),
    MetricSpec(
        name="event_outbox_backlog_messages",
        kind=MetricKind.GAUGE,
        help_text="Pending outbox messages at the latest housekeeping snapshot.",
    ),
    MetricSpec(
        name="event_outbox_oldest_pending_seconds",
        kind=MetricKind.GAUGE,
        help_text="Age of the oldest pending outbox message at the latest snapshot.",
    ),
    MetricSpec(
        name="event_audit_outbox_oldest_pending_seconds",
        kind=MetricKind.GAUGE,
        help_text="Age of the oldest undelivered audit intent at the latest snapshot.",
    ),
)

REGISTRY: MappingProxyType[str, MetricSpec] = MappingProxyType({spec.name: spec for spec in _SPECS})


def spec_for(name: str) -> MetricSpec:
    """Return the registered spec or raise for an unregistered metric name."""

    spec = REGISTRY.get(name)
    if spec is None:
        raise ValueError("metric name is not registered")
    return spec


def validate_counter(name: str, outcome: str) -> MetricSpec:
    """Validate one counter emission against the registry."""

    spec = spec_for(name)
    if spec.kind is not MetricKind.COUNTER or outcome not in spec.outcomes:
        raise ValueError("metric label is not allowlisted")
    return spec


def validate_observation(name: str) -> MetricSpec:
    """Validate one histogram observation against the registry."""

    spec = spec_for(name)
    if spec.kind is not MetricKind.HISTOGRAM:
        raise ValueError("metric is not a registered histogram")
    return spec


def validate_gauge(name: str) -> MetricSpec:
    """Validate one gauge update against the registry."""

    spec = spec_for(name)
    if spec.kind is not MetricKind.GAUGE:
        raise ValueError("metric is not a registered gauge")
    return spec
