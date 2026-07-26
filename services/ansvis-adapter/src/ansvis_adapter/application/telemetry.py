"""Low-cardinality ingestion metrics and approved operational alert evaluation.

The metric vocabulary comes from the shared `metrics_registry_v1`; this module never widens it.
"""

from __future__ import annotations

from camera_ai_metrics import validate_counter, validate_gauge, validate_observation

from ansvis_adapter.domain.ingestion import (
    AlertSeverity,
    EventOperationalSnapshot,
    OperationalAlert,
)


class NullMetricsSink:
    """Validate the bounded metric vocabulary while emitting no runtime telemetry."""

    def increment(self, metric: str, *, outcome: str) -> None:
        validate_counter(metric, outcome)

    def observe(self, metric: str, *, seconds: float) -> None:
        validate_observation(metric)
        if seconds < 0:
            raise ValueError("observed duration must be non-negative")

    def set_gauge(self, metric: str, *, value: float) -> None:
        validate_gauge(metric)
        if value < 0:
            raise ValueError("gauge value must be non-negative")


class EvaluateOperationalAlerts:
    """Evaluate only thresholds approved by the non-functional requirements baseline."""

    WARNING_OLDEST_MESSAGE_SECONDS = 120
    CRITICAL_OLDEST_MESSAGE_SECONDS = 600

    def execute(self, snapshot: EventOperationalSnapshot) -> tuple[OperationalAlert, ...]:
        alerts: list[OperationalAlert] = []
        if snapshot.failed_messages > 0:
            alerts.append(
                OperationalAlert(
                    code="EVENT_OUTBOX_DLQ_UNTRIAGED",
                    severity=AlertSeverity.CRITICAL,
                )
            )
        if snapshot.oldest_pending_seconds > self.WARNING_OLDEST_MESSAGE_SECONDS:
            severity = AlertSeverity.WARNING
            if snapshot.oldest_pending_seconds > self.CRITICAL_OLDEST_MESSAGE_SECONDS:
                severity = AlertSeverity.CRITICAL
            alerts.append(
                OperationalAlert(
                    code="EVENT_OUTBOX_OLDEST_MESSAGE",
                    severity=severity,
                )
            )
        return tuple(alerts)
