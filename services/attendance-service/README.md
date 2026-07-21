# Attendance Service

The Attendance Service owns daily student attendance state and the append-only links/corrections
that explain it. This baseline is an internal application boundary only: it does not expose a
public FastAPI route, call another service database, store media, or make disciplinary decisions.

## Data and behavior

- Owns `attendance.attendance_records`, `attendance.attendance_event_links`, and
  `attendance.attendance_corrections` only.
- Uses the caller-supplied, approved school IANA timezone to derive the attendance date.
- Enforces one record per school, student, and date and one link per normalized event/link type.
- Accepts only trusted logical UUID references. The normalized event payload, subject producer
  identifiers, profiles, biometrics, images, media, and URLs are not accepted.
- Treats missing or sub-threshold decision confidence as `pending_review`.
- Treats consent `blocked` as non-mutating. If the daily record already exists, a minimized
  `rejected` link may be appended; otherwise no attendance row or link is created.
- Requires an approved retention instant to be injected by the active policy. No duration is
  invented here.

Corrections are typed and append-only. Their actor, stable reason, approval state, and `request_id`
provide durable local audit correlation. The application outcome also contains a minimized audit
intent for delivery to the Audit Log Service by the authenticated internal integration boundary.
Public Web/Mobile activation and its reliable delivery contract remain disabled until the API
Gateway/OpenAPI authorization dependency is approved.

## Authorization

Authorization context is trusted server-side input, never copied from the command payload.

- BGH: explicitly permitted school scope.
- Teacher: explicitly permitted assigned-class scope.
- Parent/guardian: explicitly permitted linked-child reads only.
- System administrator: no business attendance access by default.

Tenant, relationship, object scope, and operation permission must all pass. A repository correction
rechecks scope after taking the database row lock.

## Configuration and local use

Copy placeholder names from `.env.example` into an approved local secret injection mechanism.
Never commit the resulting value. `ATTENDANCE_DATABASE_URI` must use `postgresql+psycopg`.

Run migration SQL generation without connecting:

```powershell
$env:APP_ENV = "test"
$env:ATTENDANCE_DATABASE_URI = "postgresql+psycopg://placeholder@127.0.0.1/placeholder"
..\..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
```

Run focused tests from the repository root after installing the editable test extra into the
workspace `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/attendance-service/tests
```

Integration tests require `ATTENDANCE_DATABASE_URI` to point to an approved, isolated, disposable
PostgreSQL database. They skip when it is absent and must never target the native development or a
production database.

## Logs and metrics

Allowlisted logs contain service, operation, result/status, stable action, and correction
`request_id` only. They exclude student/class/school/actor/event UUIDs, profile fields, raw payload,
biometrics, media/base64, tokens, secrets, and credentialed URLs.

Suggested metrics are aggregate-only:

- `attendance_ingestion_total{result,status}`
- `attendance_review_total{result}`
- `attendance_correction_total{result}`
- `attendance_repository_error_total{error_code}`

Do not place object identifiers in metric labels.

## Rollback

Application rollback means reverting the application release while preserving attendance history.
`alembic downgrade base` is allowed only for this empty, isolated baseline database. A populated or
production downgrade is destructive and requires a separately approved backup, migration, and
rollback plan.
