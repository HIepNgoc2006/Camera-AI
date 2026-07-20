# ANSVIS Adapter

This service is the HTTP Trigger boundary between ANSVIS/AIBOX and the Camera AI backend. Issue #18
implements only the bounded JSON endpoint, strict V1 parser, typed normalized event families and the
ports needed for source authentication and durable receipt storage. It does not build or train an AI
model, receive media, write PostgreSQL, or make attendance/disciplinary decisions.

## API

- `GET /healthz` reports process liveness only.
- `POST /integration/ansvis/events` accepts only `application/json` up to 65,536 bytes and validates
  `ansvis_http_trigger_v1` from `packages/ansvis-event-contract/`.

Success is deliberately conditional on durable storage:

- `202` with `outcome=accepted` only after the receipt port confirms the first committed receipt.
- `200` with `outcome=duplicate` only after the receipt port confirms a committed identical receipt.
- `503 EVENT_DURABLE_RECEIPT_UNAVAILABLE` when the durable port cannot confirm commit.

The runtime defaults deny all sources because Issue #19 owns real ANSVIS bearer authentication. A
source authenticator and a durable receipt port can be injected only through the application factory;
the production implementations are not part of this issue. Issue #61 owns PostgreSQL inbox/outbox
storage and Issue #20 owns the concrete idempotency behavior.

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

The service currently publishes no message and owns no table. The `DurableReceiptPort` is the only
application boundary for accepting an event. Its runtime implementation always fails closed, so this
skeleton cannot produce a success ACK by using memory or by silently dropping an event.

## Environment and local run

Only `APP_ENV` and `LOG_LEVEL` are read. They are non-secret labels documented in `.env.example`.
Authentication and database secrets must remain in an approved credential store/secret manager.

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/ansvis-adapter[test]"
.\.venv\Scripts\python.exe -m uvicorn ansvis_adapter.main:app --app-dir services/ansvis-adapter/src --host 127.0.0.1 --port 8010
```

The example binds only to loopback. TLS termination, trusted proxy handling, bearer verification,
rate limiting and production exposure require their approved implementation issues.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/ansvis-adapter/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Tests use synthetic identifiers and controlled fake ports. They cover schema normalization, event
family mapping, source mismatch, time replay limits, body/content-type limits, default denial,
commit-before-ACK behavior, minimal errors, logging allowlisting and OpenAPI route exposure.

## Logs and security

Logs contain only timestamp, level, service/environment, stable event name, request ID, HTTP status,
stable error code and exception class when required. Request bodies, headers, authorization values,
query strings, event attributes, subject identifiers, media, credentials and raw ANSVIS payloads are
not accepted by the logger.
