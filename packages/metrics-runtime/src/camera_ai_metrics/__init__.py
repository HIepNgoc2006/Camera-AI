"""Versioned metric registry and Prometheus runtime for Camera AI processes."""

from __future__ import annotations

from camera_ai_metrics.prometheus import PrometheusMetricsSink, start_internal_metrics_server
from camera_ai_metrics.queue_policy import (
    POLICY_VERSION,
    AlertLifecycle,
    AlertSeverity,
    CircuitDecision,
    CircuitState,
    QueueAlert,
    QueuePolicyEvaluator,
    QueueSnapshot,
    load_queue_policy,
    retry_policy_drift,
)
from camera_ai_metrics.registry import (
    MAX_LABEL_CARDINALITY,
    OUTCOME_LABEL,
    REGISTRY,
    REGISTRY_VERSION,
    MetricKind,
    MetricSpec,
    spec_for,
    validate_counter,
    validate_gauge,
    validate_observation,
)

__all__ = [
    "MAX_LABEL_CARDINALITY",
    "OUTCOME_LABEL",
    "POLICY_VERSION",
    "REGISTRY",
    "REGISTRY_VERSION",
    "MetricKind",
    "MetricSpec",
    "PrometheusMetricsSink",
    "AlertLifecycle",
    "AlertSeverity",
    "CircuitDecision",
    "CircuitState",
    "QueueAlert",
    "QueuePolicyEvaluator",
    "QueueSnapshot",
    "load_queue_policy",
    "retry_policy_drift",
    "spec_for",
    "start_internal_metrics_server",
    "validate_counter",
    "validate_gauge",
    "validate_observation",
]
