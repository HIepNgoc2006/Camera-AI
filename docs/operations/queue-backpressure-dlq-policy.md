# Queue backpressure and DLQ policy

Policy version: `queue_operational_policy_v1`

The machine-readable threshold table is
[`packages/metrics-runtime/src/camera_ai_metrics/queue_policy_v1.json`](../../packages/metrics-runtime/src/camera_ai_metrics/queue_policy_v1.json).
It is the single source of truth for event, audit, notification, and report-export queues.
Application code and alert configuration must not copy different numeric values.

## Safety boundary

Queue telemetry and alerts contain only:

- an allowlisted queue code;
- an allowlisted alert code;
- severity;
- aggregate counts, durations, and ratios.

Never attach message bodies, event or subject references, endpoint values, object-storage locators,
signed URLs, credentials, or raw errors. The metrics registry rejects unregistered names and
high-cardinality label vocabularies.

## Alert lifecycle

`QueuePolicyEvaluator` implements the exact threshold table and returns deterministic
`fired`, `active`, and `cleared` sets:

- backlog WARNING requires the depth condition to remain true for the configured duration;
- depth or drain-ETA CRITICAL is immediate;
- any non-audit DLQ arrival is WARNING, while the ten-minute sustained-profile threshold is
  CRITICAL;
- any audit-outbox DLQ arrival is CRITICAL;
- oldest-unpublished age has separate WARNING and CRITICAL thresholds;
- a downstream error ratio above the one-minute threshold opens the circuit.

At an exact boundary the alert remains at the lower state; the table uses strict `>` comparisons.
An alert clears only after a fresh aggregate snapshot no longer satisfies its condition.

## Backpressure and circuit recovery

Consumers use the shared decision:

- `closed` → normal claims;
- `open` → stop claims while ingestion/front-door rate limiting remains the pressure valve;
- after the minimum open interval, `half_open` → allow only a probe claim;
- any failed probe reopens the circuit;
- the configured consecutive successful probes close it.

Do not disable ingestion rate limiting because queue backpressure is active. Queues are never the
only flood defense.

## DLQ inspection, quarantine, and replay

1. Confirm the stable queue and alert codes, aggregate arrival count, time window, retry contract,
   and deployment version. Do not print or export payloads.
2. Inspect message metadata only through the owning service's restricted operator path. Work from
   opaque message ID, controlled error code, attempt count, and timestamps.
3. If the failure is deterministic or malformed, keep the message quarantined. Never loop a poison
   message through automatic replay.
4. Correct the code/configuration or downstream dependency first and record an allowlisted replay
   reason.
5. Use the existing owner-authorized replay path. The event path requires typed
   `ReplayAuthorization`; it emits only the bounded `event_outbox_replay_total{outcome="replayed"}`
   metric.
6. Observe queue depth, drain ETA, oldest age, DLQ arrivals, and downstream error ratio until the
   alert clears. Stop replay if the circuit reopens.
7. Audit the operator action without message content. Escalate any audit-outbox DLQ arrival as an
   incident.

Local fake-data replay evidence:

```powershell
rtk .\.venv\Scripts\python.exe -m pytest -q services/ansvis-adapter/tests/unit/test_outbox.py -k "poison_message"
```

The test forces a synthetic poison message to DLQ after bounded attempts, then replays it only after
explicit typed authorization. No real payload, endpoint, student/staff record, or credential is used.

## Retry-policy convergence gate

The default Issue #35 target for new workers is five attempts with a two-second exponential base and
bounded jitter. Notification and the report-export contract are aligned. The already-merged
`normalized_outbox_v1` event/audit paths remain pinned at a five-second base as approved versioned
exceptions; changing those semantics is explicitly outside Issue #35. `retry_policy_drift()` ensures
both exceptions stay visible and cannot silently spread to another worker. Runtime activation remains
inactive until a separate deployment/change record is approved.

## Disable and rollback

- disable alert consumption or consumer claiming; do not delete queue/DLQ contents;
- retain private queue storage and audit records;
- revert the policy/config through a reviewed deployment;
- never reset RabbitMQ, purge a DLQ, or mass-replay messages without explicit destructive-action
  approval and a rollback record.
