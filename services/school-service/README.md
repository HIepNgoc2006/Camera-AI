# School Service

School Service owns the `school` PostgreSQL schema for school, student, guardian, staff, class,
enrollment, and assignment relationships. Issue #14 delivers the physical schema and its migration
only. It does not expose a business API, decrypt profile data, process biometric data, or publish an
event.

Web and Mobile clients must never access this service or its database directly. Future profile APIs
must enter through API Gateway and remain blocked until the RBAC/ABAC and object-level authorization
policy in issue #13 is approved and implemented.

## API and events

There are no routes, consumers, or publishers in this scope. Adding them requires separately
reviewed request/response or event contracts, allowed and denied object-scope tests, audit behavior,
and retention enforcement.

## Database schema

The initial Alembic revision owns exactly these tables:

- `school.schools`
- `school.students`
- `school.guardians`
- `school.guardian_students`
- `school.staff_members`
- `school.classes`
- `school.class_enrollments`
- `school.staff_class_assignments`

Every mutable table has an opaque UUID primary key, UTC creation/update timestamps, and a positive
row version. Foreign keys remain inside the School Service schema. References owned by Identity,
Consent, Attendance, or other services must remain logical API/event references; this service must
not query their schemas.

PostgreSQL `btree_gist` supports the reviewed non-overlapping validity constraints. The migration
creates the extension if missing and deliberately does not remove this shared database capability on
downgrade. The `school` schema and all eight owned tables are removed by the reviewed downgrade.

## Sensitive data and encryption boundary

Student, guardian, and staff profile data is Critical. The schema stores only ENCV1 envelope bytes
for names, optional dates of birth, contacts, and optional external biometric subject references:

- `full_name_ciphertext`, `date_of_birth_ciphertext`, and `contact_ciphertext` are `bytea`;
- `biometric_subject_ref_ciphertext` is an opaque encrypted external reference, not a face image,
  crop, embedding, or vendor credential;
- `contact_lookup_hmac` is an exact-match LOOKUP-V1 value with its key outside PostgreSQL;
- ciphertext is never indexed or searched, and no plaintext fallback column exists.

The migration does not implement encryption or create a key. Future application code must authorize
tenant/object scope and consent/purpose before decrypting, use the approved KMS adapter, keep
plaintext out of logs/caches/traces, and fail closed if a key or policy is unavailable.

Database constraints reject cross-school guardian, enrollment, and staff assignment links. School
scope changes are also rejected while they would leave an existing relationship linked to a
different tenant.

## Environment and migration commands

The process reads `APP_ENV` and `SCHOOL_DATABASE_URI` from the environment and never auto-loads a
dotenv file. The URI is a secret-bearing runtime value even though the tracked example contains only
placeholders. Inject it through the approved local environment or secret manager and do not place it
in a command line, log, issue, or screenshot.

Install into the workspace virtual environment:

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/school-service[test]"
```

After `SCHOOL_DATABASE_URI` has been injected safely:

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/school-service/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c services/school-service/alembic.ini current
```

Do not run the downgrade against a development, staging, pilot, or production database merely to
test rollback. The following command is authorized only for the isolated fake-data test database:

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/school-service/alembic.ini downgrade base
```

Production migration requires backup/restore assessment, an approved migration identity, a change
window, and confirmation that no dependent data or service exists. This issue does not authorize a
production migration or destructive rollback.

## Tests

The integration test fails closed unless the URI points to a loopback PostgreSQL database on a
non-5432 port with a database name ending in `_test`. It upgrades from base, inspects the table,
column, foreign-key, constraint, and index inventory, inserts synthetic identifiers/encrypted bytes,
tests invalid and cross-tenant relationships, then downgrades to base.

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/school-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

If `SCHOOL_DATABASE_URI` is absent, the destructive integration test is skipped; CI and completion
evidence must run it against the isolated PostgreSQL service and show it passed.

## Logs, metrics, retention, and security

This migration-only scope emits no application log or metric. Alembic output must never include a
database URI, ciphertext, HMAC, profile field, or inserted value. Future runtime observability must
use stable operation/result labels without tenant, student, guardian, staff, or relationship IDs.

Profile and relationship lifecycle follows `RET-PROFILE`. Deactivation or consent withdrawal must
deny future processing before asynchronous disposal; exact production duration remains an approved
privacy/legal policy input. No row is hard-deleted by application behavior in this issue, and no
real profile, camera, ANSVIS, biometric, evidence, secret, dump, or backup data is used in tests.
