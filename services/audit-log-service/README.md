# Audit Log Service

Audit Log Service owns the `audit` PostgreSQL schema and the sole append-only audit evidence table,
`audit.audit_events`. Issue #16 delivers versioned ingestion validation, idempotent persistence, an
injected integrity-signing boundary, chain verification, the migration, and tests. It deliberately
does not expose query/export endpoints, run retention, provision a key, or read another service's
schema.

Audit metadata is High and can become Critical because actor, tenant, resource, action, and time can
be correlated. The service therefore accepts only opaque identifiers, stable allowlisted codes,
minimized network metadata, and controlled `audit_changes_v1` summaries.

## API and event boundary

There is no public HTTP route in this scope. A future internal API or queue consumer must call
`AppendAuditEventService` with two separate inputs:

- `AuditEventV1`, containing the publisher-controlled event fields;
- `TrustedAuditContext`, supplied from authenticated workload, actor, tenant, and retention policy
  context.

The declared `source_service` must match the authenticated service. Actor, role, school,
`retention_until`, `recorded_at`, integrity partition, event ID, hash version, and hashes cannot be
overridden by publisher payload. Sensitive actions in owning services must first persist an audit
intent in their own transactional outbox; they must not call this service inside the business
transaction or insert into the audit schema directly.

Supported actions are the approved stable taxonomy from the database contract. Unknown actions,
source/action combinations, results, resources, change fields, state keys, reference types, count
names, or policy version keys fail closed with stable redacted errors.

## Prohibited input

Do not send or store:

- names, email, phone, address, date of birth, student/staff codes, or free-text reasons;
- face images, crops, embeddings, emotion detail, media, base64, or data URIs;
- raw ANSVIS/vendor payloads or request/response body, header, or query copies;
- bucket/object keys, signed/public/credentialed URLs, or RTSP/database URLs;
- passwords, tokens, credentials, provider key identifiers, key material, ciphertext, HMAC values,
  wrapped DEKs, stack traces, or exception/provider details.

`audit_changes_v1` can contain only allowlisted field names, stable before/after state codes,
booleans, opaque UUID references, bounded non-negative counts, and policy versions. Rejected input is
never echoed in a service error or log.

## Database and append-only behavior

The migration creates exactly `audit.audit_events`, its approved constraints/indexes, and mutation
guard triggers. Runtime `UPDATE`, `DELETE`, and `TRUNCATE` are denied. `(source_service,
source_event_id)` is unique:

- an identical canonical duplicate returns the existing event;
- different canonical content with the same identity returns `AUDIT_DUPLICATE_CONFLICT`.

Writers take a PostgreSQL transaction advisory lock for the server-derived daily integrity
partition. Each event is canonicalized and linked to the prior event with a 32-byte keyed integrity
value. `HmacSha256IntegritySigner` accepts injected key bytes but never loads, persists, logs, or
exports a key. Production key resolution/provisioning remains a separately approved KMS/secret
manager integration. Scheduled checkpoints/WORM export are also follow-up scope.

The service never joins or queries Identity, School, Consent, Events, Evidence, or another service's
schema. Their IDs remain logical opaque references.

## Environment and migration commands

Tracked examples contain placeholders only. Runtime reads `APP_ENV` and `AUDIT_DATABASE_URI` from the
injected environment and never auto-loads dotenv. Do not place a real URI in a command line, log,
issue, screenshot, `.local/`, or tracked file.

Install into the workspace virtual environment:

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/audit-log-service[test]"
```

After `AUDIT_DATABASE_URI` has been injected safely:

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/audit-log-service/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c services/audit-log-service/alembic.ini current
```

Downgrade removes the entire audit schema and is destructive. It is authorized only for the isolated
loopback, non-5432, fake-data test database whose name ends in `_test`:

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/audit-log-service/alembic.ini downgrade base
```

Never run that downgrade against development, staging, pilot, or production. Production migration
requires backup/restore assessment, approved runtime/migration roles, KMS readiness, a change window,
and a rollback plan that preserves audit evidence.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/audit-log-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Unit tests cover action/schema/change allowlists, trusted-context binding, size/nesting and forbidden
values, stable redacted errors, canonicalization, signer behavior, architecture boundaries, config,
and migration source scope. The integration test applies/downgrades the migration, inspects exact
inventory, appends fake events, checks identical/conflicting duplicates, serializes concurrent chain
writes, rejects runtime mutation, and proves tamper detection.

The integration test skips when `AUDIT_DATABASE_URI` is absent and fails closed unless it points to a
loopback PostgreSQL database on a non-5432 port with a `_test` database name. CI must supply this
isolated fake-data database so the integration evidence cannot be skipped.

## Logs, metrics, retention, and rollback

Safe application logs contain only service, operation, source, action, result, request ID, and stable
reason code. They exclude actor/tenant/resource IDs, changes, rejected values, hashes, network
addresses, URLs, payloads, and database/provider detail. Recommended metrics use bounded labels:
accepted, duplicate, rejected, conflict, append failure, append latency, chain verification failure,
and checkpoint age by source/action/result only.

Retention execution is not active in this issue. Audit evidence follows `RET-AUDIT-LOG`: retain with
restricted access until an exact approved policy and legal-hold decision permit partition retirement.
Business-row deletion must never silently delete audit evidence. A future retention role must use the
approved dry-run, approval, checkpoint/tombstone, and reconciliation workflow rather than bypassing
the append-only trigger.

Application rollback can stop publishers or revert the service release while retaining the table and
evidence. Database downgrade is not a production rollback strategy. Integrity failure must isolate
the affected partition, alert security using redacted metadata, and must not repair, overwrite, or
delete evidence automatically.
