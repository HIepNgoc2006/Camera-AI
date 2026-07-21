# ANSVIS Adapter

This service is the HTTP Trigger boundary between ANSVIS/AIBOX and the Camera AI backend. Issue #18
provides the bounded JSON endpoint, strict V1 parser and typed normalized event families. Issue #19
adds the strict `ansvis-login-bearer-v1` validation core and registered-source binding. Issue #20 adds
the versioned idempotency descriptor and durable-receipt consistency contract. The service does not
issue tokens, build or train an AI model, receive media, write PostgreSQL, or make attendance or
disciplinary decisions.

## API

- `GET /healthz` reports process liveness only.
- `POST /integration/ansvis/events` accepts only `application/json` up to 65,536 bytes and validates
  `ansvis_http_trigger_v1` from `packages/ansvis-event-contract/`.

Success is deliberately conditional on durable storage:

- `202` with `outcome=accepted` only after the receipt port confirms the first committed receipt.
- `200` with `outcome=duplicate` only after the receipt port confirms a committed identical receipt.
- `409 EVENT_IDEMPOTENCY_CONFLICT` when one identity is reused with different canonical content.
- `503 EVENT_DURABLE_RECEIPT_UNAVAILABLE` when the durable port cannot confirm commit.

The runtime defaults still deny authentication, idempotency derivation and durable receipts. Issue #19
provides a fixed HS256 JWS verifier, but it can authenticate only when signing-key, revocation and
registered-source adapters are explicitly injected through the application factory. Issue #20 provides
`ContractIdempotencyDeriver`, but it must also be injected and its fallback HMAC key must come from an
approved secret-manager adapter. Real secret-manager/source/revocation adapters and persistent stores
are not part of these issues. Issue #61 owns PostgreSQL inbox/outbox storage and concurrency control.

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

The service currently publishes no message and owns no table. `IdempotencyDeriver` and
`DurableReceiptPort` are the application boundaries for identifying and accepting an event. Their
runtime defaults always fail closed, so this skeleton cannot produce a success ACK by using memory or
by silently dropping an event.

## Environment and local run

Only `APP_ENV` and `LOG_LEVEL` are read. They are non-secret labels documented in `.env.example`.
There is deliberately no environment variable for a signing key, Bearer token or fallback-idempotency
key. Authentication, idempotency and database secrets must remain in an approved credential
store/secret manager and be supplied through approved adapters in a later production-wiring issue.

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/ansvis-adapter[test]"
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

## Logs and security

Logs contain only timestamp, level, service/environment, stable event name, request ID, HTTP status,
stable error code and exception class when required. Request bodies, headers, authorization values,
query strings, event attributes, subject identifiers, media, credentials and raw ANSVIS payloads are
not accepted by the logger.
