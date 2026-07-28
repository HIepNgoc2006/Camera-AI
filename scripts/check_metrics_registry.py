"""Validate the shared metric registry: bounded vocabulary, kind conventions, baseline names.

The registry is code (`packages/metrics-runtime`), so structural invariants are enforced at
construction; this checker re-verifies them independently, confirms the baseline entries the
platform already emits are present, and fails closed on any drift. It reads no runtime state
and prints only metric names and counts.
"""

from __future__ import annotations

import sys

BASELINE_METRICS = (
    "event_ingestion_total",
    "event_ingestion_rejections_total",
    "event_outbox_dispatch_total",
    "event_outbox_replay_total",
    "event_operational_alerts_total",
    "event_audit_delivery_total",
    "event_consent_gate_total",
    "event_ingestion_ack_seconds",
    "event_outbox_enqueue_to_publish_seconds",
    "event_outbox_backlog_messages",
    "event_outbox_oldest_pending_seconds",
    "event_audit_outbox_oldest_pending_seconds",
    "notification_dispatch_total",
    "notification_dlq_arrivals_total",
    "notification_reauthorization_seconds",
    "notification_retry_backlog_messages",
    "evidence_lifecycle_total",
    "evidence_access_total",
    "evidence_reconciliation_total",
    "evidence_attachment_ratio_events_total",
)
FORBIDDEN_LABEL_MARKERS = (
    "camera",
    "school",
    "student",
    "subject",
    "tenant",
    "token",
    "uuid",
)


def run_checks() -> list[str]:
    """Return a list of failure descriptions; empty means the registry is healthy."""

    failures: list[str] = []
    try:
        from camera_ai_metrics import (
            MAX_LABEL_CARDINALITY,
            REGISTRY,
            REGISTRY_VERSION,
            MetricKind,
        )
    except Exception as error:  # pragma: no cover - import failure is itself the finding
        return [f"metrics registry import failed: {type(error).__name__}"]

    if REGISTRY_VERSION != "metrics_registry_v1":
        failures.append("registry version drifted from metrics_registry_v1")
    for name in BASELINE_METRICS:
        if name not in REGISTRY:
            failures.append(f"baseline metric missing: {name}")
    for spec in REGISTRY.values():
        if len(spec.outcomes) > MAX_LABEL_CARDINALITY:
            failures.append(f"cardinality above bound: {spec.name}")
        if spec.kind is MetricKind.COUNTER and not spec.outcomes:
            failures.append(f"counter without outcome vocabulary: {spec.name}")
        for outcome in spec.outcomes:
            if any(marker in outcome for marker in FORBIDDEN_LABEL_MARKERS):
                failures.append(f"identifier-shaped label value: {spec.name}/{outcome}")
        if spec.kind is MetricKind.HISTOGRAM and list(spec.buckets) != sorted(set(spec.buckets)):
            failures.append(f"histogram buckets not ascending: {spec.name}")
    return failures


def main() -> int:
    failures = run_checks()
    if failures:
        for failure in failures:
            print(f"metrics_registry=FAIL {failure}")
        return 1
    from camera_ai_metrics import REGISTRY, REGISTRY_VERSION

    print("metrics_registry=PASS")
    print(f"policy_version={REGISTRY_VERSION}")
    print(f"metrics_checked={len(REGISTRY)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
