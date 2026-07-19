# Consent Service

Consent Service owns the first executable subset of the `privacy` PostgreSQL schema for Issue #15.
It records versioned purposes, current subject consent state, immutable consent events, and one
transactional audit intent for every consent change. It is a Critical-data boundary: identifiers are
opaque, processing is purpose-specific, and every missing or ambiguous gate denies by default.

This baseline exposes no public HTTP route and performs no biometric processing. Public actor/object
authorization depends on Issues #13 and #59, so callers must supply server-resolved trusted context.
The service never queries Identity, School, Audit, Evidence, Events, or another service's schema.

## Internal application boundary

`ConsentApplicationService` provides four internal use cases:

- `register_purpose`: inserts a new draft or active immutable purpose version after a trusted purpose
  management decision;
- `request_consent`: binds tenant, subject, actor, authority relationship, and authority reference from
  `TrustedConsentContext`, then creates a `pending` record;
- `transition_consent`: applies the approved state machine with optimistic concurrency;
- `evaluate`: returns a non-throwing allow/deny decision for an exact consent, purpose, subject, scope,
  time, relationship, and optional expected version.

Strict V1 DTOs reject unknown fields, zero IDs, duplicate/unapproved scopes, naive timestamps,
free-text reasons, URLs, payload-like evidence, and invalid request/idempotency formats. Parse errors
are stable and never echo rejected content.

The initial state machine is deliberately narrow:

```text
pending -> granted -> withdrawn | restricted | expired
       \-> denied
```

`denied`, `withdrawn`, `restricted`, and `expired` are terminal in this baseline. A later approved
workflow must create a new policy/consent record rather than silently restoring a terminal state.
Withdrawal or restriction updates the canonical row and appends its event/audit intent in the same
transaction, so processing denies immediately even when the future publisher or lifecycle worker is
unavailable.

## Evaluation contract

Allow requires all of the following at evaluation time:

- the tenant-scoped consent and its exact purpose exist;
- the trusted subject type/ID matches and the authority/object relationship remains verified;
- the caller supplied the exact purpose ID and, when used, current consent row version;
- status is `granted`, `valid_from` has begun, and `valid_to` has not elapsed;
- the purpose is active for the tenant and within its version validity window;
- every requested scope is present in both the consent and the purpose data categories.

Missing, cross-tenant, wrong-subject, wrong-purpose, unverified relationship, pending, denied,
withdrawn, restricted, expired, future, inactive, wrong-scope, and stale-version cases deny with a
stable code. Cross-tenant absence is intentionally indistinguishable from not found to avoid an
identifier oracle.

## Database ownership and audit intent

The migration creates exactly these Issue #15 objects:

- `privacy.purposes` — versioned declared purposes;
- `privacy.consents` — one mutable, non-deletable current row per tenant/subject/purpose;
- `privacy.consent_events` — append-only change history and idempotency evidence;
- `privacy.consent_audit_outbox` — minimized publisher-ready audit intent in the same transaction.

`privacy.retention_policies` and `privacy.data_subject_requests` remain deferred to their approved
lifecycle issues. The outbox is a required physical extension to the logical dictionary because
Issue #15 requires durable audit intent without a cross-schema write. Its typed fields contain stable
codes and opaque IDs only; there is no arbitrary JSON, consent document, signature, URL, image,
embedding, ANSVIS payload, evidence media, credential, secret, or free-text reason. Publishing to
Audit Log Service and delivery-state retry handling are follow-up scope.

Each event is unique by `(school_id, idempotency_key)` and stores a SHA-256 semantic request
fingerprint. An identical retry returns the existing outcome; conflicting content fails with
`CONSENT_DUPLICATE_CONFLICT`. Row locks and `row_version` serialize competing transitions. Database
triggers deny event update/delete/truncate and consent delete/truncate.

Audit actions are `CONSENT_REQUESTED`, `CONSENT_GRANTED`, `CONSENT_DENIED`, `CONSENT_WITHDRAWN`,
`CONSENT_EXPIRED`, and `CONSENT_RESTRICTED`. The Audit Log Service policy registry accepts these
actions from `consent-service` only.

## Environment and migration commands

Runtime reads `APP_ENV` and `CONSENT_DATABASE_URI` from injected environment only. It never loads a
dotenv file and never logs or echoes the URI. Tracked examples contain placeholders only.

```powershell
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/consent-service[test]"
.\.venv\Scripts\python.exe -m alembic -c services/consent-service/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c services/consent-service/alembic.ini current
```

Downgrade drops the `privacy` schema and is destructive. It is authorized only for a loopback,
non-5432, fake-data database whose name ends in `_test`:

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/consent-service/alembic.ini downgrade base
```

Never run that downgrade against development, staging, pilot, or production. Production activation
requires approved actor/object authorization, privacy/legal policy, runtime/migration roles, backup
and rollback review, retention/DSR workflows, and outbox publishing/monitoring.

## Tests and verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/consent-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Unit tests cover strict schemas, trusted-context binding, purpose/scope/status/time/relationship/version
deny cases, terminal transitions, redacted errors/logs, configuration, architecture separation, no
public route, and migration scope. The integration test applies and downgrades the migration, inspects
the owned schema, verifies identical/conflicting idempotency, exact allow, immediate withdrawal deny,
competing transition serialization, one event plus audit intent per committed change, and database
mutation guards.

The integration test skips when `CONSENT_DATABASE_URI` is absent and fails closed unless the URI is a
loopback PostgreSQL database on a non-5432 port with a `_test` name. CI supplies an isolated fake-data
database, so integration verification must not be skipped there.

## Logs, metrics, retention, and rollback

Safe change logs contain only service, operation, action, stable status/result/reason, and request ID.
Decision logs contain only service, operation, allow/deny, and stable reason code. They exclude tenant,
subject, authority, actor, purpose/consent/resource IDs, scope lists, timestamps, evidence refs,
fingerprints, payloads, URLs, and database/provider detail. Optional evidence references are limited
to an approved record-type prefix plus an opaque UUID; they are never media or document content.

Recommended bounded metrics are decision count by reason, change count by action/result, version
conflict count, duplicate/conflict count, outbox pending age/count, and repository latency/failure.
Labels must not contain tenant/person/resource IDs.

Retention, consent-proof anonymization, deletion, legal hold, DSR, downstream cache/event revocation,
and backup re-application are not activated here. Current consent status remains authoritative and
withdrawal evidence is retained as restricted minimized proof. Application rollback may stop callers
or revert the release while preserving rows/events/outbox; dropping the schema is not a production
rollback strategy.
