# ANSVIS Adapter

This service is the HTTP Trigger boundary between ANSVIS/AIBOX and the Camera AI backend. Issue #18
provides the bounded JSON endpoint, strict V1 parser and typed normalized event families. Issue #19
adds the strict `ansvis-login-bearer-v1` validation core and registered-source binding. Issue #20 adds
the versioned idempotency descriptor and durable-receipt consistency contract. Issue #61 adds the
co-located Event Ingestion persistence core and bounded transactional outbox. Issue #139 wires the
fail-closed consent gate into that ingestion path for face/emotion events. The service does not
issue tokens, build or train an AI model, receive/store media, resolve biometric identity, or make
attendance or disciplinary decisions.

## API

- `GET /healthz` reports process liveness only.
- `POST /integration/ansvis/events` accepts only `application/json` up to 65,536 bytes and validates
  `ansvis_http_trigger_v1` from `packages/ansvis-event-contract/`.

Success is deliberately conditional on durable storage:

- `202` with `outcome=accepted` only after the receipt port confirms the first committed receipt.
- `200` with `outcome=duplicate` only after the receipt port confirms a committed identical receipt.
- `409 EVENT_IDEMPOTENCY_CONFLICT` when one identity is reused with different canonical content.
- `503 EVENT_DURABLE_RECEIPT_UNAVAILABLE` when the durable port cannot confirm commit.
- `503 EVENT_CONSENT_UNAVAILABLE` when a face/emotion event cannot obtain a consent decision; the
  deferred receipt is durable and the source must retry the identical event. A consent-`blocked`
  event is acknowledged like any accepted event, so the ACK never discloses consent state.

The runtime defaults still deny authentication, idempotency derivation and durable receipts. Issue #19
provides a fixed HS256 JWS verifier, but it can authenticate only when signing-key, revocation and
registered-source adapters are explicitly injected through the application factory. Issue #20 provides
`ContractIdempotencyDeriver`, but it must also be injected and its fallback HMAC key must come from an
approved secret-manager adapter. Issue #61 provides `PostgresEventIngestionRepository`, but it remains
fail closed until an authoritative source/camera/task scope resolver, an approved retention duration
and a secret-injected PostgreSQL engine are supplied. Real secret-manager/source/revocation wiring and
production process assembly remain outside this issue.

Authentication requires exactly one HTTPS `Authorization: Bearer ...` value. The verifier requires
`alg=HS256`, `typ=JWT`, a stable `kid`, exact issuer/audience, opaque `sub` and revocable `jti`, strict
NumericDate values and a maximum five-minute token lifetime. It binds the verified subject to one
active source namespace, tenant and school. Missing, duplicate, combined, malformed, expired, revoked,
unknown or dependency-unavailable inputs fail closed with stable masked errors.

## Idempotency contract

Derivation occurs only after authentication, normalized schema validation, authoritative tenant/school
binding and replay-window validation. It follows `http-trigger-policy-v1.json` exactly:

- a present source event ID produces `idem_source_v1_<sha256>` from tenant, authenticated source
  namespace and source event ID;
- a missing source event ID requires track and detection identifiers and produces
  `idem_fallback_v1_<hmac-sha256>` from the approved V1 fallback projection and a secret-managed key;
- `sha256:<digest>` fingerprints the canonical normalized event, its idempotency key and time-policy
  version while excluding correlation ID, so a tracing-only retry remains identical;
- the receipt must echo the exact key/fingerprint and a valid committed receipt ID. Missing providers,
  policy drift, invalid key material, unconfirmed/mismatched receipts and unexpected adapter failures
  fail closed without a success ACK.

The key and fingerprint are internal opaque values. They are not part of the HTTP ACK/error response or
structured logs. The port contract requires one accepted result, duplicate success only for the same
fingerprint, and `EVENT_IDEMPOTENCY_CONFLICT` for changed content. Issue #61 must enforce that contract
atomically with a unique PostgreSQL inbox key; the adapter deliberately has no production in-memory
ledger.

Errors are exactly:

```json
{
  "error_code": "EVENT_SCHEMA_INVALID",
  "message": "Request rejected.",
  "request_id": "req_test_ansvis_0001"
}
```

## Normalized event families

The external DTO is mapped to framework-free domain types for:

- attendance and timekeeping face observations;
- suspected littering, PPE, smoking and uniform violations;
- emotion insight observations;
- camera and task health transitions.

These types carry only the contract allowlist. There is no field for image/video, base64, raw vendor
payload, camera address, RTSP URL, credential, embedding or arbitrary metadata. A face observation is
an observation, not proof of attendance or an automated decision.

## Events and database

The Event Ingestion component owns only these tables in the `events` schema:

- `ingestion_receipts`: append-only source/key checksum gate;
- `normalized_events`: one minimized normalized record per accepted receipt;
- `event_detections`: controlled non-media detection attributes without producer subject IDs;
- `processing_attempts`: append-only conflict, publisher and authorized replay outcomes;
- `outbox_messages`: versioned normalized messages with a 30-second claim lease.

The receipt insert, normalized event, optional detection and outbox message commit in one PostgreSQL
transaction. `UNIQUE (source_id, idempotency_key)` makes identical retries return the original receipt
and changed-content reuse records a stable `EVENT_IDEMPOTENCY_CONFLICT` quarantine attempt. Scope IDs
come only from `EventScopeResolver`; the repository neither queries nor foreign-keys another service's
schema. Retention has no code default and must be supplied from an approved bounded policy.

Outbox delivery is at-least-once. Claims are leased for 30 seconds; `claim_batch` leases up to 50 due
messages in recorded order under `FOR UPDATE SKIP LOCKED` and `mark_published_batch` acknowledges the
whole batch in one transaction (`claim_next`/`mark_published` delegate to the same paths). Failures
use 5/10/20/40-second exponential base delays plus bounded 0–20% jitter, and the fifth failure becomes
`failed`/dead-lettered. Replay accepts only an
explicit typed operator authorization with an opaque actor UUID and allowlisted reason code; it writes
an append-only replay attempt before returning the message to `pending`. A concrete broker publisher
is injected through `EventPublisher`; the default application does not start a worker or guess a queue
connection. The supervised drain runtime lives in `workers/event-outbox-worker/` (`DrainOutboxBatch`
use case + RabbitMQ publisher under confirms, exchange `camera-ai.events.v1`). Downstream consumers
must remain idempotent.

Stored JSONB contracts are allowlisted as `event_metadata_v1`, `detection_attributes_v1` and
`normalized_outbox_v1`. They cannot contain raw ANSVIS payloads, media URLs/binary, base64, RTSP data,
credentials, face embeddings or producer `subject_external_id`. This component never turns an
observation into an identity or business decision.

### Consent gate (Issue #139)

Face and emotion event types are evaluated through the `ConsentGate` port before anything is
persisted. The gate maps `attendance.face.observed -> attendance`, `timekeeping.face.observed ->
timekeeping` and `insight.emotion.observed -> emotion` and calls the consent-service internal
evaluation port with `(tenant_ref, school_ref, subject_ref, purpose, policy_version)` under the
pinned `consent_gate_v1` contract. Every stored event row and outbox payload carries the resolved
`consent_gate_status` plus `consent_policy_version`; the migration CHECK forbids `not_evaluated` at
rest for these types. Outcomes:

- `allowed` / `not_required`: the full normalized record, detection row and outbox message persist.
  Non-biometric event types map to `not_required` explicitly without calling the gate.
- `blocked` (unresolvable subject, no/withdrawn/expired/restricted consent, inactive or ambiguous
  purpose, unsupported policy version): only the minimized rejected link persists — scope, type,
  time, correlation, model/config versions — with no confidence, no detection row and no outbox
  message, and exactly one `EVENT_CONSENT_DENIED` audit intent (deterministic identity per receipt)
  is enqueued in the same transaction. Blocked is final: the append-only trigger and DB CHECKs make
  a later flip to a business record impossible.
- gate unreachable/ambiguous transport failure: the receipt commits as `deferred` with
  `EVENT_CONSENT_UNAVAILABLE`, no event row exists, an audit intent records the deferral once, and
  the request fails `503` so the source retries idempotently. The retry re-evaluates and
  materializes under the original receipt; the receipt row keeps its append-only `deferred` history
  (aggregate `accepted_receipts` therefore counts only first-pass accepted receipts). Retries are
  bounded by the source retry policy and the 300-second replay window.

The dispatch paths add a defense-in-depth fan-out guard: any face/emotion outbox message whose
payload does not prove `allowed`/`not_required` is refused terminally (`publish_status=refused`, a
`consent-guard` dead-letter attempt with `EVENT_CONSENT_BLOCKED`, one audited
`EVENT_CONSENT_DENIED` intent) and `replay_failed` cannot resurrect it. The default runtime gate is
`UnavailableConsentGate`, so an unwired deployment defers every biometric event instead of guessing.
`ConsentServiceGate` composes the consent-service evaluation port in-process with its own
`CONSENT_DATABASE_URI` engine — no cross-schema SQL.

Telemetry vocabulary comes from the shared `metrics_registry_v1` (`packages/metrics-runtime`) —
low-cardinality only:

- `event_ingestion_total{outcome=accepted|duplicate|rejected|conflict}`;
- `event_outbox_dispatch_total{outcome=empty|published|retry_scheduled|dead_lettered|refused}`;
- `event_consent_gate_total{outcome=allowed|blocked|not_required|unavailable}`;
- `event_outbox_replay_total{outcome=replayed}`;
- `event_ingestion_ack_seconds` (histogram, request-to-ACK) and
  `event_outbox_enqueue_to_publish_seconds` (histogram, record-to-confirmed-publish);
- `event_outbox_backlog_messages` / `event_outbox_oldest_pending_seconds` gauges (worker
  housekeeping) and `event_operational_alerts_total`.

The runnable app defaults to the registry-backed Prometheus sink; when `METRICS_PORT` is non-zero
(default 9464, `0` under `APP_ENV=test`) the exposition is served on a **loopback-only** internal
port via the app lifespan — never through the API gateway. Tests inject `NullMetricsSink`.

The internal `snapshot()` boundary exposes aggregate accepted, pending, published, failed, retry,
conflict, delayed and oldest-pending values only; it has no tenant, school, camera, event, person or
evidence identifiers. `EVENT_OUTBOX_OLDEST_MESSAGE` is warning above 120 seconds and critical above
600 seconds. Any untriaged failed/DLQ message raises `EVENT_OUTBOX_DLQ_UNTRIAGED` at critical. These
are the approved baseline thresholds; post-pilot tuning requires the operational owner and cannot
silence the signal. The ANSVIS Integration operations role owns triage: stop automated replay, inspect
only sanitized receipt/attempt metadata, resolve the broker/consumer cause, authorize one bounded
replay, then confirm backlog drain. The default no-op sink validates metric names but does not expose a
public metrics endpoint; deployment must inject its internal telemetry exporter and access control.

## Environment and local run

`APP_ENV` and `LOG_LEVEL` are non-secret runtime labels. Alembic additionally requires
`EVENT_DATABASE_URI`, which is secret-bearing, parsed without a printable representation and never
loaded from a dotenv file by application code. Inject it from the approved credential store or secret
manager. `CONSENT_DATABASE_URI` (same loader guarantees) is read only when deployment wires
`ConsentServiceGate`; when it is absent the composition must keep the fail-closed
`UnavailableConsentGate`. There is deliberately no environment variable for a signing key, Bearer
token or fallback idempotency key; those values remain behind injected provider ports.

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/ansvis-adapter[test]"
.\.venv\Scripts\python.exe -m alembic -c services/ansvis-adapter/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn ansvis_adapter.main:app --app-dir services/ansvis-adapter/src --host 127.0.0.1 --port 8010
```

The example binds only to loopback. Runtime secret/source adapter wiring, TLS termination, trusted
proxy handling, rate limiting and production exposure require their approved implementation issues.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/ansvis-adapter/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Tests use synthetic identifiers and controlled fake ports. They cover schema normalization, event
family mapping, strict Bearer/JWS parsing, algorithm/signature/claim/time boundaries, revocation and
provider failures, duplicate/combined headers, registered-source and tenant/school mismatch, time
replay limits, body/content-type limits, primary/fallback idempotency vectors, ten-retry duplicate
behavior, changed-content conflict, cross-scope separation, provider/receipt failure, default denial,
commit-before-ACK behavior, masked errors and logs, logging allowlisting and OpenAPI route exposure.
Event-ingestion coverage adds migration ownership/constraints, JSONB minimization, ten identical
retries, conflicting-content quarantine, concurrent first-write behavior, outbox leasing and bounded
retry/dead-letter/replay state. The PostgreSQL integration test skips unless `EVENT_DATABASE_URI` is
injected and fails closed unless it names a loopback, non-5432 database ending in `_test`.
The shared sanitized payload matrix also runs every allowlisted event type and each schema rejection
case through `IngestAnsvisEvent` and `ContractIdempotencyDeriver`.

## Operations and rollback

Apply and roll back the schema only through Alembic after injecting the database URL securely:

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/ansvis-adapter/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c services/ansvis-adapter/alembic.ini downgrade base
```

Before rollback, stop ingestion and the outbox dispatcher, verify no accepted receipt or unpublished
message must be preserved, and follow the approved backup/restore process. The downgrade drops the
owned `events` schema and is destructive; it is not an operational reset procedure. Never replay by
editing rows manually, and never delete/quarantine records to make a queue appear healthy.

## Logs and security

Logs contain only timestamp, level, service/environment, stable event name, request ID, HTTP status,
stable error code and exception class when required. Request bodies, headers, authorization values,
query strings, event attributes, subject identifiers, media, credentials and raw ANSVIS payloads are
not accepted by the logger.
