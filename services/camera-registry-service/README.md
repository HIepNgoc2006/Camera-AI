# Camera Registry Service

Camera Registry Service owns the first executable subset of the `camera` PostgreSQL schema for
Issue #60. It manages High-sensitivity zone and non-secret camera metadata plus one primary opaque
ANSVIS source/task reference per camera. It does not connect to a stream, configure ANSVIS, process
events, store media, or expose a public HTTP route.

Public camera administration and end-user authorization remain blocked by Issues #13 and #59.
Callers of this baseline must provide a server-resolved `TrustedRegistryContext`; no payload field can
grant tenant, zone, purpose, actor, or assignment authority.

## Internal application boundary

`CameraRegistryApplicationService` exposes only internal use cases:

- `register_zone`, `update_zone`, and `deactivate_zone`;
- `register_camera`, `update_camera`, `map_camera`, and `deactivate_camera`;
- tenant/zone/purpose-scoped `get_zone` and `get_camera` lookups.

Commands are strict V1 DTOs. Unknown fields, zero UUIDs, unapproved or duplicate purposes, empty
updates, naive authority, malformed request/idempotency values, and operational names containing URL,
credential, token, address, or secret markers fail with stable redacted errors. A camera credential can
only be represented by an opaque value matching `sec_v1_<32-96 URL-safe characters>`; the value is a
lookup handle for a future secret-manager adapter, not a password or URL.

Zone/purpose compatibility is deliberately narrow. The baseline supports approved cameras at gates,
yards, hallways, kitchens, and an explicit `other` non-classroom zone; classroom is not accepted.
Kitchen PPE can only be assigned to a kitchen zone. A camera purpose must be allowed by the zone and
the trusted actor assignment.

## Lifecycle and concurrency

Zones start `active` and become terminal `inactive`. Cameras start `pending`; future health work may
use `online`/`offline`, while this baseline only deactivates them to terminal `disabled`. A zone cannot
be deactivated while it still owns an active camera. Disabled cameras and inactive zones cannot be
silently reactivated.

Every mutable record has `row_version`. Update, mapping, and deactivation require an exact expected
version and use row locks plus a compare-and-update predicate. Competing changes produce one commit
and one `CAMERA_VERSION_CONFLICT`; they never overwrite a newer configuration.

Each mutation is unique by `(school_id, idempotency_key)` in the audit outbox and stores a SHA-256
semantic fingerprint. An identical retry returns the existing outcome without another business change
or audit intent. Reusing the key with different content fails with `CAMERA_DUPLICATE_CONFLICT`.

## Database ownership and primary mapping

The migration creates exactly these Issue #60 objects:

- `camera.zones` — tenant zone, sensitivity, lifecycle, and approved purpose codes;
- `camera.cameras` — tenant camera metadata, lifecycle, opaque credential reference, primary logical
  source/task IDs, mapping purpose, and schedule/config versions;
- `camera.camera_audit_outbox` — one typed minimized audit intent per committed mutation.

The outbox is the issue-required technical extension to the two approved business tables. It contains
only opaque UUIDs, stable codes, changed-field names, versions, fingerprint, and delivery state. It has
no arbitrary JSON, display name, credential reference/value, host/IP, RTSP/ONVIF URL, license, ANSVIS
payload, PII, biometric data, media, evidence reference, or free-text note. A later publisher may emit
the approved `CAMERA_MAPPING_CHANGED` event to Audit Log Service; this service never writes the
`audit` schema directly.

`source_id` and `task_id` are logical references only. The database has no foreign key or query into
the Integration schema. The single primary pair is enough for the JSON-ingestion baseline; future
many-to-many ANSVIS task/camera mappings remain owned by Integration Service and Issue #90.

The database forbids duplicate tenant codes and duplicate primary `(school, source, task)` mappings.
A composite `(school_id, zone_id)` foreign key also prevents a camera from referencing another
tenant's zone even if repository checks are bypassed. Hard delete/truncate is blocked; deactivation
is required. `last_seen_at` is present from the approved dictionary but is not written by this
baseline because health polling belongs to follow-up scope.

## API and events

There is no FastAPI application, router, Web/Mobile route, camera discovery endpoint, stream probe,
or ANSVIS client in this service. It consumes no external events. Its only future publication contract
is the pending transactional audit intent; transport, retries, and delivery monitoring are follow-up
work.

Issue #17 may later resolve an already-normalized camera reference through this internal boundary. It
must not send raw vendor fields or query this schema directly.

## Environment and migration commands

Runtime reads `APP_ENV` and `CAMERA_DATABASE_URI` from injected environment only. It never loads a
dotenv file and never logs or echoes the URI. Tracked examples contain placeholders only. This issue
adds no unreviewed third-party dependency; it uses the same pinned Python/PostgreSQL stack already
approved in the repository.

```powershell
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/camera-registry-service[test]"
.\.venv\Scripts\python.exe -m alembic -c services/camera-registry-service/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c services/camera-registry-service/alembic.ini current
```

Downgrade drops the `camera` schema and is destructive. It is authorized only for a loopback,
non-5432, fake-data database whose name ends in `_test`:

```powershell
.\.venv\Scripts\python.exe -m alembic -c services/camera-registry-service/alembic.ini downgrade base
```

Never run that downgrade against development, staging, pilot, or production. Production activation
requires approved public authorization, secret-manager resolution, runtime/migration roles, backup,
retention, outbox publishing/monitoring, and rollback review.

## Tests and verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/camera-registry-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Unit tests cover strict DTOs, zone/purpose compatibility, trusted assignment, secret-reference
rejection, lifecycle, redacted logging/configuration, framework separation, no public route, and
migration scope. The integration test applies and downgrades the migration in an isolated loopback
non-5432 `_test` database, inspects owned objects, verifies identical/conflicting retry behavior,
primary mapping uniqueness, optimistic concurrency, terminal deactivation, zone-in-use denial,
atomic audit-intent counts, and hard-delete protection.

The integration test skips when `CAMERA_DATABASE_URI` is absent and fails closed unless the URI is a
loopback PostgreSQL database on a non-5432 port with a `_test` name. CI supplies an isolated fake-data
database, so the integration test must not be skipped there.

## Logs, metrics, retention, and rollback

Safe change logs contain only service, operation, action/change code, resource type, lifecycle status,
request ID, and stable result. They exclude tenant/actor/resource IDs, zone/source/task references,
names, purpose lists, timestamps, credential references, fingerprints, payloads, URLs, database
details, and provider details.

Recommended bounded metrics are mutation count by change/result, version/duplicate/mapping conflict
count, outbox pending age/count, and repository latency/failure. Labels must not contain tenant,
camera, zone, source, task, or actor IDs.

Retention/revocation workers are not activated here. Camera and mapping metadata follows
`RET-CAMERA-CONFIG`: deactivate first, then later remove stale mapping/secret references through an
approved lifecycle workflow while retaining minimized tombstone/audit proof. Application rollback may
stop callers or revert a release while preserving registry/outbox records; dropping the schema is not
a production rollback strategy.
