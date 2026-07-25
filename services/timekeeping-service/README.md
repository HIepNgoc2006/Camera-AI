# Timekeeping Service

The Timekeeping Service owns staff/teacher shift versions, assignments, daily shift records, and
the append-only event/correction history that explains each record. This baseline is an internal
application boundary only. It exposes no public route, reads no other service schema, stores no
media/biometric value, and makes no payroll or disciplinary decision.

## Data and behavior

The service owns exactly these PostgreSQL tables:

- `timekeeping.shifts`
- `timekeeping.staff_shift_assignments`
- `timekeeping.timekeeping_records`
- `timekeeping.timekeeping_event_links`
- `timekeeping.timekeeping_corrections`

Shift rows are versioned by school/code/version. A partial unique index permits at most one active
version per school/code, and a deferred lifecycle constraint requires exactly one active version
after a code has ever been activated. All-draft versions are allowed before first activation. Active
business fields are database-protected from mutation. Replacing an active version must be an atomic
trusted operation that retires the old row and activates the new draft in one transaction.

Every shift has an installed IANA timezone, explicit overnight flag, exact local start/end, and
bounded check-in/check-out grace. Overnight events are assigned to the work date whose scheduled
start or end is closest to the event, depending on link type. An exact tie, missing/low confidence,
supporting-only event, conflicting late/early outcome, or unmatched check-in/out routes to `review`.

Active staff assignments cannot overlap for the same school/staff. The database serializes and
checks assignment ranges, including open-ended ranges. Records are unique by school, staff,
work-date, and shift version. Event links are idempotent by `(normalized_event_id, link_type)`.

Only trusted logical UUID references are accepted. Producer staff identifiers, profiles, face
images/crops/embeddings, media/base64, raw ANSVIS payloads, RTSP details, signed URLs, and secrets are
not accepted or stored.

Consent behavior is fail closed:

- biometric processing requires `allowed`;
- non-biometric trusted processing may use `not_required`;
- `blocked` or a missing biometric allowance never creates or changes a timekeeping record;
- if the target record already exists, a minimized append-only `rejected` link may be stored.

Retention is an injected timestamp from an active policy. This baseline does not invent or hard-code
a production duration. AI output cannot be the sole basis for an employment decision.

Corrections use typed statuses/timestamps and stable reason codes only; there is no free-form PII
field. The append-only row records actor, request correlation, approval state, and approver when
decided. The application also emits a minimized audit intent for the Audit Log Service boundary.

## Authorization

Authorization context is trusted server-side input and never copied from command payloads.

- Staff self: own record only, with explicit read/correction-request permission.
- HR: explicitly authorized staff set/unit or approved school-wide scope.
- BGH: approved school-wide scope.
- System administrator: denied business timekeeping access by default.

School, relationship, object scope, operation permission, and approval authority must all pass. A
repository correction rechecks scope after locking the row. Staff and HR/BGH actors cannot approve
their own protected correction when their actor-to-staff identity matches the record.

## Configuration and local use

Copy placeholder names from `.env.example` into an approved local secret injection mechanism. Never
commit a real value. `TIMEKEEPING_DATABASE_URI` must use `postgresql+psycopg`.

Generate migration SQL without connecting:

```powershell
$env:APP_ENV = "test"
$env:TIMEKEEPING_DATABASE_URI = "postgresql+psycopg://placeholder@127.0.0.1/placeholder"
..\..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
```

Run focused tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/timekeeping-service/tests
```

Repository integration tests require `TIMEKEEPING_DATABASE_URI` to point to an approved, isolated,
disposable loopback PostgreSQL database whose name ends in `_test`. They skip when it is absent and
must never target the native development or a production database.

## Logs and metrics

Allowlisted logs contain service, operation, result/status, stable action, and correction
`request_id` only. They exclude staff/school/actor/shift/event UUIDs, profiles, raw payload,
biometrics, media/base64, tokens, secrets, and credentialed URLs.

Suggested aggregate-only metrics:

- `timekeeping_ingestion_total{result,status}`
- `timekeeping_review_total{reason}`
- `timekeeping_correction_total{result}`
- `timekeeping_assignment_conflict_total`
- `timekeeping_repository_error_total{error_code}`

Object identifiers must never be metric labels.

## Rollback

Application rollback means reverting the application release while preserving timekeeping history.
Disable internal event dispatch first if a release is unsafe; do not delete or rewrite records,
links, or corrections.

`alembic downgrade base` is permitted only for an empty, isolated baseline database. A populated or
production downgrade would destroy schema/history and requires separate authorization plus an
approved backup, migration, reconciliation, and recovery plan. Shift/assignment and native
PostgreSQL data must never be reset merely to retry a migration.
