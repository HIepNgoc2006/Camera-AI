"""Low-cardinality ingestion metrics and approved operational alert evaluation."""

from __future__ import annotations

from ansvis_adapter.domain.ingestion import (
    AlertSeverity,
    EventOperationalSnapshot,
    OperationalAlert,
)

ALLOWED_METRICS = frozenset(
    {
        "event_ingestion_total",
        "event_outbox_dispatch_total",
        "event_outbox_replay_total",
    }
)
ALLOWED_OUTCOMES = frozenset(
    {
        "accepted",
        "conflict",
        "dead_lettered",
        "duplicate",
        "empty",
        "published",
        "rejected",
        "replayed",
        "retry_scheduled",
    }
)


class NullMetricsSink:
    """Validate the bounded metric vocabulary while emitting no runtime telemetry."""

    def increment(self, metric: str, *, outcome: str) -> None:
        if metric not in ALLOWED_METRICS or outcome not in ALLOWED_OUTCOMES:
            raise ValueError("metric label is not allowlisted")


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
