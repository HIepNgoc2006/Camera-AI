# Notification Service

The Notification Service owns versioned notification intents, per-recipient delivery state,
protected endpoint references, attempts, cancellations, and a minimized audit outbox. This baseline
is internal and inactive by default: it has no public route, provider adapter, provider credential,
network dispatch, production activation, or Web/Mobile UI.

It accepts only a closed `NotificationIntentV1` contract from an authenticated, delegated source
service. A caller supplies opaque UUID references, an approved content class and template version,
recipient candidates, channel, expiry, purpose context, request/correlation IDs, and an idempotency
key. Arbitrary title, body, HTML, media, URL, provider payload, personal text, endpoint value, face
data, or raw ANSVIS payload is rejected.

## Security and authorization

Recipient/relationship and endpoint ownership are Critical data. Intent, delivery, cancellation,
and audit state are High, or Critical when linked to a child or biometric purpose.

The application fails closed unless all applicable checks are current:

- trusted allowlisted source identity and `service.notification.request`;
- source delegation, exact tenant/school binding, and active
  `notification_privacy_policy_v1`;
- approved content class, template code/version, source state, purpose and unexpired source;
- current recipient role, relationship, object permission, purpose and consent;
- active recipient plus owned, verified, preferred endpoint for push/email;
- available authorization dependencies.

The batch authorization port is called again before every dispatch/retry and notification open.
Positive authorization is never cached across attempts. Cancellation authenticates the source and
supports consent, permission, relationship, recipient, endpoint, source, purpose, and policy
revocation triggers. A stale open is concealed as `NOTIFICATION_NOT_AVAILABLE`.

Device/email endpoint values cross only the `EndpointProtector` boundary. The shared crypto runtime
stores ENCV1 ciphertext and a LOOKUP-V1 digest. Values are never returned by an API, audit, metric,
exception, or log. Endpoint registration/revocation requires the internal
`service.notification.endpoint.manage` permission and records an opaque audit event.

## Content contract

The immutable policy maps six content classes to one generic template, permission, purpose, allowed
source state, and recipient-role set. All channels contain only versioned localization codes,
opaque notification reference, and expiry.

- In-app may additionally contain an opaque resource reference, creation time, generic title code,
  and action-available flag.
- Push may contain a generic title code and the allowlisted `notification_inbox` route.
- Email may contain a generic subject code and the same allowlisted route.

Push/email cannot contain a resource locator. PostgreSQL repeats this allowlist as a JSONB
constraint and explicitly rejects known sensitive field names.

## Owned storage and events

The service owns only the `notification` PostgreSQL schema:

- `notification_intents`
- `recipient_deliveries`
- `delivery_attempts`
- `recipient_endpoints`
- `notification_cancellations`
- `audit_outbox`

There are no cross-schema foreign keys or direct reads of another service schema. Intent
idempotency is `(tenant_id, idempotency_key)` plus a SHA-256 content fingerprint. Delivery
uniqueness is `(notification_id, recipient_ref, channel)`. Attempts and cancellations are
append-only and their audit records are transactionally placed in the local audit outbox using the
shared audit-producer contract.

The service reuses the shared RabbitMQ/outbox/DLX topology from the event-outbox worker. It defines
no second exchange or queue. Real provider/result consumers remain a separately approved adapter.
The minimized `DeadLetterEnvelope` contains only delivery ID, notification ID, attempt count,
controlled reason category, and timestamp—never rendered content or endpoint data.

## Retry and capacity evidence

The recorded fake-data morning profile assumes 60 concurrent classes, 30 guardians per class, and
1,800 recipient deliveries over a ten-minute triangular arrival window. The resulting modeled peak
is 6 deliveries/second. The local synthetic test exercises 60 deliveries/second, ten times the
modeled peak.

Authorization uses batches of 30 with a per-check p95 budget of 50 ms. At the local load-test rate,
two batches/second consume 10% of one sequential authorization lane
(`60 / 30 * 0.050 = 0.10`). The deterministic load test processes the 1,800 fake authorization
records inside the 50 ms local CPU budget; it performs no network or provider action.

Retry is capped at five attempts with exponential backoff from two seconds plus bounded jitter.
In-flight retries are capped at 5,000, matching the service's approved queue-depth safety bound.
Once the cap is reached no attempt is recorded, preventing retry storms from multiplying
re-authorization load without bound. The fifth failed attempt or a permanent controlled provider
category enters dead-letter reconciliation.

## Internal API and errors

There is deliberately no FastAPI router. Trusted adapters call:

- `NotificationApplicationService.accept_intent`
- `DeliveryApplicationService.record_provider_result`
- `DeliveryApplicationService.authorize_open`
- `DeliveryApplicationService.cancel`
- `EndpointApplicationService.register` / `revoke`

The internal adapter maps failures to exactly `error_code`, `message`, and `request_id`. Protected
recipient, endpoint, policy, and object failures are concealed. Raw dependency or provider errors
must never cross this boundary.

## Configuration and local use

`.env.example` contains the placeholder name only. Supply `NOTIFICATION_DATABASE_URI` through the
approved local secret injection mechanism; never commit or print a real value. The URI must use
`postgresql+psycopg`.

Generate offline migration SQL without connecting:

```powershell
$env:NOTIFICATION_DATABASE_URI = "postgresql+psycopg://placeholder@127.0.0.1/placeholder_test"
..\..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
```

Run focused verification from the repository root:

```powershell
.\.venv\Scripts\ruff.exe check services/notification-service
.\.venv\Scripts\python.exe -m mypy services/notification-service/src
.\.venv\Scripts\python.exe -m pytest -q services/notification-service/tests
```

The repository integration test requires `NOTIFICATION_DATABASE_URI` to target an approved,
disposable loopback PostgreSQL database whose name ends in `_test`. It applies the migration,
exercises fake intent/idempotency/outbox and ENCV1 endpoint behavior, rolls back to base, and skips
when the isolated database is absent. Never point it at the native development or production
database.

## Logs, metrics, and audit

Logs use an explicit allowlist: service, operation, outcome, stable error code, request ID and
correlation ID. They exclude object/recipient/endpoint UUIDs, rendered content, personal data,
biometrics, media, provider response text, tokens, secrets, ciphertext and lookup digests.

Registered aggregate-only metrics:

- `notification_dispatch_total{outcome}`
- `notification_dlq_arrivals_total{outcome}`
- `notification_reauthorization_seconds`
- `notification_retry_backlog_messages`

Object IDs and unbounded provider values are forbidden metric labels. Audit actions include
dispatch granted/denied, delivered, retry, dead letter, open granted/denied, cancellation, expiry,
and endpoint change/revocation. Audit payloads contain only opaque references, stable outcome/reason,
policy versions and request correlation.

## Activation, disable, and rollback

This baseline cannot send a real notification. Activation remains blocked until the named
Privacy/Legal, Security/Ops, business-owner, and provider approvals exist, provider adapters and
credentials are separately authorized, shared API/error alignment is complete, and an approved
deployment/change record verifies monitoring, retention, reconciliation, backup and rollback.

To disable a faulty release, stop the internal intent/dispatch adapter and outbox drain for this
service while preserving database and DLQ state for reconciliation. Revert application code without
deleting records.

`alembic downgrade base` is allowed only for an empty, isolated baseline test database. On a
populated or production database it is destructive and requires explicit authorization, an
approved backup, migration/reconciliation plan and tested recovery. Never reset notification,
native PostgreSQL, or workspace Docker data merely to retry a migration.
