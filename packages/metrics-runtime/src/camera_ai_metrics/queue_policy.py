"""Versioned, identifier-free queue backpressure and DLQ policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from importlib import resources
from types import MappingProxyType
from typing import Any, cast

POLICY_VERSION = "queue_operational_policy_v1"
QUEUE_CODES = frozenset({"audit_outbox", "event_outbox", "notification", "report_export"})
ALERT_CODES = frozenset(
    {
        "QUEUE_DEPTH",
        "QUEUE_DLQ",
        "QUEUE_DOWNSTREAM_CIRCUIT",
        "QUEUE_OLDEST_UNPUBLISHED",
    }
)


class AlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ClaimMode(StrEnum):
    NORMAL = "normal"
    STOP = "stop"
    PROBE = "probe"


@dataclass(frozen=True, slots=True, kw_only=True)
class QueueAlert:
    queue_code: str
    alert_code: str
    severity: AlertSeverity

    def __post_init__(self) -> None:
        if self.queue_code not in QUEUE_CODES or self.alert_code not in ALERT_CODES:
            raise ValueError("queue alert must use allowlisted stable codes")


@dataclass(frozen=True, slots=True, kw_only=True)
class QueueSnapshot:
    """Aggregate-only queue state; no payload, endpoint, or subject fields are permitted."""

    queue_code: str
    depth_messages: int = 0
    depth_breach_seconds: int = 0
    drain_eta_seconds: float = 0
    dlq_arrivals_10m: int = 0
    oldest_unpublished_seconds: int = 0
    downstream_attempts_1m: int = 0
    downstream_errors_1m: int = 0

    def __post_init__(self) -> None:
        if self.queue_code not in QUEUE_CODES:
            raise ValueError("queue code is not allowlisted")
        values = (
            self.depth_messages,
            self.depth_breach_seconds,
            self.drain_eta_seconds,
            self.dlq_arrivals_10m,
            self.oldest_unpublished_seconds,
            self.downstream_attempts_1m,
            self.downstream_errors_1m,
        )
        if any(value < 0 for value in values):
            raise ValueError("queue snapshot values must be non-negative")
        if self.downstream_errors_1m > self.downstream_attempts_1m:
            raise ValueError("downstream errors cannot exceed attempts")

    @property
    def downstream_error_ratio(self) -> float:
        if self.downstream_attempts_1m == 0:
            return 0.0
        return self.downstream_errors_1m / self.downstream_attempts_1m


@dataclass(frozen=True, slots=True, kw_only=True)
class AlertLifecycle:
    active: tuple[QueueAlert, ...]
    fired: tuple[QueueAlert, ...]
    cleared: tuple[QueueAlert, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CircuitDecision:
    state: CircuitState
    claim_mode: ClaimMode


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return cast(dict[str, Any], value)


@lru_cache(maxsize=1)
def load_queue_policy() -> MappingProxyType[str, Any]:
    raw = resources.files("camera_ai_metrics").joinpath("queue_policy_v1.json").read_text("utf-8")
    value = _object(json.loads(raw), "policy")
    if value.get("policy_version") != POLICY_VERSION:
        raise ValueError("queue policy version mismatch")
    thresholds = _object(value.get("thresholds"), "thresholds")
    queues = _object(value.get("queues"), "queues")
    retry_contracts = _object(value.get("retry_contracts"), "retry_contracts")
    if set(queues) != QUEUE_CODES or set(retry_contracts) != QUEUE_CODES:
        raise ValueError("queue policy must cover every allowlisted queue")
    required_thresholds = {
        "warning_depth_messages",
        "warning_depth_for_seconds",
        "critical_depth_messages",
        "critical_drain_eta_seconds",
        "warning_dlq_arrivals",
        "critical_dlq_arrivals_over_10m",
        "warning_oldest_unpublished_seconds",
        "critical_oldest_unpublished_seconds",
        "circuit_open_error_ratio",
        "circuit_minimum_open_seconds",
        "half_open_successes_to_close",
        "target_max_attempts",
        "target_base_backoff_seconds",
    }
    if not required_thresholds <= set(thresholds):
        raise ValueError("queue policy threshold table is incomplete")
    expected_dlq_arrivals = int(
        int(thresholds["sustained_profile_events_per_second"])
        * 600
        * float(thresholds["dlq_rate_critical_ratio"])
    )
    if int(thresholds["critical_dlq_arrivals_over_10m"]) != expected_dlq_arrivals:
        raise ValueError("DLQ rate threshold does not match the sustained profile")
    if (
        int(thresholds["target_max_attempts"]) != 5
        or int(thresholds["target_base_backoff_seconds"]) != 2
        or thresholds.get("jitter_required") is not True
    ):
        raise ValueError("target retry contract drifted from Issue #35")
    return MappingProxyType(value)


class QueuePolicyEvaluator:
    """Evaluate exact Issue #35 thresholds and stable alert lifecycle."""

    def __init__(self) -> None:
        policy = load_queue_policy()
        self._thresholds = _object(policy["thresholds"], "thresholds")
        self._queues = _object(policy["queues"], "queues")

    def evaluate(self, snapshot: QueueSnapshot) -> tuple[QueueAlert, ...]:
        alerts: list[QueueAlert] = []
        depth_severity: AlertSeverity | None = None
        if snapshot.depth_messages > int(
            self._thresholds["critical_depth_messages"]
        ) or snapshot.drain_eta_seconds > float(self._thresholds["critical_drain_eta_seconds"]):
            depth_severity = AlertSeverity.CRITICAL
        elif snapshot.depth_messages > int(
            self._thresholds["warning_depth_messages"]
        ) and snapshot.depth_breach_seconds >= int(self._thresholds["warning_depth_for_seconds"]):
            depth_severity = AlertSeverity.WARNING
        if depth_severity is not None:
            alerts.append(self._alert(snapshot, "QUEUE_DEPTH", depth_severity))

        queue = _object(self._queues[snapshot.queue_code], "queue")
        dlq_severity: AlertSeverity | None = None
        if (
            snapshot.dlq_arrivals_10m > 0
            and bool(queue["audit_strict"])
            or snapshot.dlq_arrivals_10m > int(self._thresholds["critical_dlq_arrivals_over_10m"])
        ):
            dlq_severity = AlertSeverity.CRITICAL
        elif snapshot.dlq_arrivals_10m >= int(self._thresholds["warning_dlq_arrivals"]):
            dlq_severity = AlertSeverity.WARNING
        if dlq_severity is not None:
            alerts.append(self._alert(snapshot, "QUEUE_DLQ", dlq_severity))

        oldest_severity: AlertSeverity | None = None
        if snapshot.oldest_unpublished_seconds > int(
            self._thresholds["critical_oldest_unpublished_seconds"]
        ):
            oldest_severity = AlertSeverity.CRITICAL
        elif snapshot.oldest_unpublished_seconds > int(
            self._thresholds["warning_oldest_unpublished_seconds"]
        ):
            oldest_severity = AlertSeverity.WARNING
        if oldest_severity is not None:
            alerts.append(self._alert(snapshot, "QUEUE_OLDEST_UNPUBLISHED", oldest_severity))

        if snapshot.downstream_error_ratio > float(self._thresholds["circuit_open_error_ratio"]):
            alerts.append(self._alert(snapshot, "QUEUE_DOWNSTREAM_CIRCUIT", AlertSeverity.CRITICAL))
        return tuple(alerts)

    def lifecycle(
        self, previous: tuple[QueueAlert, ...], snapshot: QueueSnapshot
    ) -> AlertLifecycle:
        active = self.evaluate(snapshot)
        previous_by_key = {(item.queue_code, item.alert_code): item for item in previous}
        active_by_key = {(item.queue_code, item.alert_code): item for item in active}
        fired = tuple(
            item for key, item in active_by_key.items() if previous_by_key.get(key) != item
        )
        cleared = tuple(item for key, item in previous_by_key.items() if key not in active_by_key)
        return AlertLifecycle(active=active, fired=fired, cleared=cleared)

    def circuit(
        self,
        snapshot: QueueSnapshot,
        *,
        current: CircuitState,
        open_seconds: int = 0,
        half_open_successes: int = 0,
    ) -> CircuitDecision:
        if open_seconds < 0 or half_open_successes < 0:
            raise ValueError("circuit counters must be non-negative")
        threshold = float(self._thresholds["circuit_open_error_ratio"])
        if current is CircuitState.CLOSED:
            next_state = (
                CircuitState.OPEN
                if snapshot.downstream_error_ratio > threshold
                else CircuitState.CLOSED
            )
        elif current is CircuitState.OPEN:
            next_state = (
                CircuitState.HALF_OPEN
                if open_seconds >= int(self._thresholds["circuit_minimum_open_seconds"])
                else CircuitState.OPEN
            )
        elif snapshot.downstream_errors_1m > 0:
            next_state = CircuitState.OPEN
        elif half_open_successes >= int(self._thresholds["half_open_successes_to_close"]):
            next_state = CircuitState.CLOSED
        else:
            next_state = CircuitState.HALF_OPEN
        mode = {
            CircuitState.CLOSED: ClaimMode.NORMAL,
            CircuitState.OPEN: ClaimMode.STOP,
            CircuitState.HALF_OPEN: ClaimMode.PROBE,
        }[next_state]
        return CircuitDecision(state=next_state, claim_mode=mode)

    @staticmethod
    def _alert(snapshot: QueueSnapshot, code: str, severity: AlertSeverity) -> QueueAlert:
        return QueueAlert(
            queue_code=snapshot.queue_code,
            alert_code=code,
            severity=severity,
        )


def retry_policy_drift() -> tuple[str, ...]:
    """Return stable queue codes that differ from the Issue #35 target retry contract."""

    policy = load_queue_policy()
    thresholds = _object(policy["thresholds"], "thresholds")
    contracts = _object(policy["retry_contracts"], "retry_contracts")
    target_attempts = int(thresholds["target_max_attempts"])
    target_base = int(thresholds["target_base_backoff_seconds"])
    return tuple(
        queue_code
        for queue_code in sorted(QUEUE_CODES)
        if int(_object(contracts[queue_code], "retry contract")["observed_max_attempts"])
        != target_attempts
        or int(_object(contracts[queue_code], "retry contract")["observed_base_backoff_seconds"])
        != target_base
    )
