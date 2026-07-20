# Time synchronization and timezone policy

Policy ID `camera_event_time`, version `time_policy_v1`, status `active`. Owner:
`platform_operations`; approver: `project_owner`; purpose: `event_integrity`; data class: High.
The machine-readable contract is
[`packages/time-policy/time-policy-v1.json`](../../packages/time-policy/time-policy-v1.json).

This baseline governs Backend, API Gateway, ANSVIS/AIBOX integration, PostgreSQL, audit/logging and
business-time conversion. It does not change an operating-system clock, NTP source, camera setting,
ANSVIS task or production infrastructure.

## Normative baseline

- Internet event timestamps follow the project subset of [IETF RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339):
  full date, uppercase `T`, full time and explicit uppercase `Z` or numeric `±HH:MM` offset.
- Hosts synchronize UTC using an approved NTPv4 implementation aligned with
  [IETF RFC 5905](https://datatracker.ietf.org/doc/html/rfc5905). Prefer Network Time Security where
  supported, following [IETF RFC 8915](https://datatracker.ietf.org/doc/html/rfc8915), or an approved
  authenticated private time service with equivalent operational control.
- Business timezone identifiers come from the [IANA Time Zone Database](https://www.iana.org/time-zones).
  The default is `Asia/Ho_Chi_Minh`. A school override requires an approved immutable configuration
  version; abbreviations such as `ICT`, a bare `+07:00`, browser timezone or host-local timezone are
  not business-zone authority.
- The numerical thresholds below are project policy, not values mandated by the RFCs. Pilot evidence
  may change them only through a new policy version and compatibility review.

Leap seconds are rejected by `time_policy_v1` because the current Backend/PostgreSQL parsing path does
not preserve `:60` consistently. An announced leap second must be handled by the approved host time
service; changing application behavior requires a new policy version.

## Clock ownership and authority

| Boundary | Owner | Required behavior |
|---|---|---|
| API Gateway/Backend hosts | Platform Operations | Synchronize system UTC from approved sources; expose offset/stratum/sync state without source endpoint details |
| PostgreSQL host/service | Database Operations | Synchronize host UTC; database/session timezone UTC; use `timestamptz`; never infer business date from server-local timezone |
| ANSVIS/AIBOX host | ANSVIS Operations | Synchronize UTC; emit offset-aware timestamps; report health through approved operational metadata |
| Camera clock | Camera Operations | Synchronize to an approved managed source; no arbitrary public endpoint in project configuration |
| School business timezone | School configuration owner | Approve an IANA zone and immutable config version; default `Asia/Ho_Chi_Minh` |
| Event receipt timestamp | API Gateway/ingestion owner | Capture trusted `server_received_at` at first authenticated server boundary; clients/vendors cannot supply or overwrite it |

Wall-clock time orders business events. Monotonic process clocks measure duration, timeout, retry and
latency. Never calculate elapsed time from wall-clock values that may step during synchronization.

## Timestamp contract

1. Transport accepts only RFC 3339 values with explicit `Z` or numeric offset and at most six
   fractional digits. Canonical output is UTC with six fractional digits and a `Z` suffix.
2. Naive timestamps, lowercase designators, spaces instead of `T`, unknown offset `-00:00`, invalid
   dates, unsupported leap seconds and precision beyond microseconds fail closed.
3. `vendor_event_time` is vendor-provided High metadata. `server_received_at` is trusted server time.
   Both are retained as distinct typed fields; the vendor value never replaces receipt time.
4. PostgreSQL stores instants in `timestamptz` under UTC session settings. Reports convert from UTC
   using the business timezone and the timezone-config version effective for the record.
5. Attendance date, lateness, shift boundary and report grouping use the versioned school business
   timezone—not the browser, container, database or host-local timezone.
6. A source configured to emit local offset time must match its approved IANA configuration at that
   instant. UTC `Z` output is always preferred. A mismatch is quarantined or rejected with a stable
   code; it is never silently reinterpreted.

Event transport never accepts local wall time. For approved schedule/admin input, a nonexistent local
time is rejected. An ambiguous daylight-saving time requires explicit `earlier_instant` or
`later_instant`; the chosen UTC instant, IANA zone and config version are stored together. The default
Vietnam zone currently has no DST ambiguity, but an approved override must still follow this rule.

## Drift, replay and fail-closed states

| Control | `time_policy_v1` value | Boundary behavior |
|---|---:|---|
| Clock sample interval | 60 seconds | Monitor each server/ANSVIS role; do not expose endpoint/host identifiers as metric labels |
| Healthy clock offset | absolute offset ≤ 1 second | Normal processing |
| Warning clock offset | > 1 and ≤ 5 seconds | Alert after three consecutive samples; continue only with trusted receipt time and increased observation |
| Critical clock offset | > 5 seconds | Mark time source unhealthy; time-sensitive ingestion fails with `TIME_SOURCE_UNHEALTHY` until five healthy samples |
| Future event tolerance | 30 seconds | Greater values reject with `TIME_EVENT_FUTURE` |
| Past/replay window | 300 seconds | Older values reject with `TIME_REPLAY_WINDOW_EXCEEDED`; no normal-ingestion backfill bypass |
| Nonce retention | 600 seconds | A source/nonce pair cannot be reused; duplicate remains rejected through the retention window |

The boundaries are inclusive: exactly +30 seconds and exactly -300 seconds are accepted if all other
authentication, schema, source, mapping and idempotency checks pass. Replay acceptance never means a
business event is unique; Issue #17 must still enforce source-scoped nonce/signature and idempotency.
An approved backfill/import is a separate authenticated workflow with its own policy, audit and rate
limits; it must not widen the live webhook window.

## Stable outcomes and processing order

Relevant codes are versioned in the machine contract. At minimum Issue #17 must distinguish malformed,
naive, unknown-offset, precision, future, replay, ambiguous/nonexistent local time, unapproved zone and
unhealthy source outcomes. Errors and logs return only the stable code and request/correlation ID;
they never echo the rejected timestamp, source endpoint, camera/task topology or payload.

The ingestion order is:

1. Capture trusted `server_received_at` and request/correlation ID.
2. Verify receiver clock health; critical state fails closed.
3. Authenticate the active source and enforce size/rate limits.
4. Validate signed timestamp/nonce against the 300-second replay contract.
5. Validate schema, parse `vendor_event_time`, normalize to UTC and compare future/past bounds.
6. Validate source/camera/task mapping and configured timezone/version when applicable.
7. Apply canonical hash/idempotency and persist receipt/outbox atomically before ACK.

## Monitoring, evidence and escalation

Required bounded metrics are `clock_offset_seconds`, `clock_sync_state`,
`time_validation_total{result_code}`, `event_time_delta_seconds` histogram and
`time_replay_rejected_total`. Labels may include environment and bounded node/source role; they must
not include school, camera, task, event, host, IP, URL, PII or raw timestamp values.

Logs use UTC, request/correlation ID, service, environment and stable result code only. Health evidence
records policy version, tool/agent version, sample period, aggregate offset/state, reviewer role and
review time. Do not attach raw ANSVIS payloads, production endpoint details or clock configuration.

- Warning: Platform Operations investigates synchronization/source reachability. Three consecutive
  warning samples open an operational alert.
- Critical: Platform Operations owns containment; Backend owner confirms fail-closed behavior;
  Security is notified on replay/signature spikes or suspected time manipulation.
- Recovery: five consecutive healthy samples are required before clearing critical state. Never
  suppress an alert or force a clock step during active ingestion without approved change control.

## Sanitized verification

[`timestamps.synthetic.json`](../../packages/test-fixtures/ansvis/timestamps.synthetic.json) contains
only deterministic fake instants. It covers UTC, numeric offsets, default business conversion,
future/past boundaries, malformed/naive/unknown-offset/high-precision values, drift states and
ambiguous/nonexistent local time.

Run:

```powershell
.\.venv\Scripts\python.exe scripts/quality.py time-policy
.\.venv\Scripts\python.exe scripts/quality.py all
```

Issue #17 E2E must submit those cases through the Backend boundary and assert response code, durable
receipt outcome, normalized UTC, no duplicate business record, masked log and PostgreSQL `timestamptz`
value. Report/business tests must assert `Asia/Ho_Chi_Minh` grouping plus a synthetic approved IANA
override. No fixture may contain a real school, person, camera, endpoint, credential or raw payload.

## Change control and rollback

The JSON contract is immutable after activation. A threshold, timezone behavior, error semantic or
parsing change requires `time_policy_v2` (or later), compatibility fixtures, security/operations
review, staged rollout and an explicit effective time. Existing records retain their policy and
timezone-config versions.

Rollback means selecting the prior approved policy version and disabling/quarantining ingestion that
cannot satisfy it. Because v1 has no prior project version, rollback from v1 is fail-closed suspension
of dependent Issue #17 ingestion until an approved replacement exists. It never means changing host
clocks, weakening replay checks, editing v1 in place or reinterpreting stored timestamps.
