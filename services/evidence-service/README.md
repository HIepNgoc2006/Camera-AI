# Evidence Storage Service

## Purpose

This service is the sole boundary for private evidence objects. It stores only metadata and
`ENCV1`-encrypted object/provider locators in PostgreSQL; image/video bytes remain in a private
S3-compatible object store. Signed upload/access material is short-lived and is never persisted,
logged, audited, or returned by metadata endpoints.

The implementation policy is `evidence_access_policy_v1`. Runtime activation remains fail-closed
until the named Privacy/Legal, Security/Ops, and business-owner approvals exist. Building this
service does not activate that policy.

## Data and lifecycle

- Evidence images with faces/biometrics: Critical.
- Other violation evidence: High.
- States: `pending_upload -> quarantined -> available -> delete_pending -> deleted`.
- `missing` and `failed` model reconciliation or verification failure.
- Only `available` objects with a clean scan, active retention, resolved consent, and resolved
  legal-hold state can be accessed.
- Physical row deletion is blocked; deletion is a lifecycle transition with object-store deletion
  and audit evidence.

Tables owned in PostgreSQL schema `evidence`:

- `evidence_objects`
- `evidence_links`
- `audit_outbox`

No table has media binary, base64, an unencrypted object key/provider version, or a signed URL.

## Service contract

The internal adapter in `evidence_service.api.internal` exposes:

- upload request (metadata only), returning a 60-second constrained private POST form;
- upload finalization after size, SHA-256, MIME/extension/magic, dimensions/duration and object
  version verification;
- trusted clean-scan completion;
- access request for metadata, thumbnail, original, download, or export.

Public Web/Mobile callers must continue through API Gateway. Authentication middleware supplies a
trusted `RequestContext`; caller-provided actor, tenant, school, permission, or purpose fields are
not accepted in request payloads.

Signed GET defaults to 60 seconds, is capped at 300 seconds, and is capped at 120 seconds for
export delivery. Missing and unauthorized resources both return `EVIDENCE_NOT_FOUND`.

## Object storage

The exact S3 client is `minio==7.2.20`. Startup must call the adapter's private-bucket verification:

- the configured bucket reference is allowlisted;
- the bucket exists and has no anonymous allow policy;
- versioning is enabled;
- enabled lifecycle rules cover every configured retention class using the exact
  `retention_days=<days>` object tag.

`provision_private_bucket` creates only the allowlisted private bucket, enables versioning and
installs tagged expiry rules for the approved 15/30/180/365-day classes plus one-day cleanup of
incomplete multipart uploads. The constrained POST policy binds the opaque key, content type,
maximum byte size and exact retention tag so a caller cannot select a longer lifecycle.

Local HTTP endpoints are allowed only on loopback. Remote endpoints require TLS. The opaque key
shape is `evidence/v1/<random-shard>/<random-128-bit-id>` and contains no tenant, school, student,
event, camera, or task identifier.

Image uploads are capped at 10 MiB; video uploads are capped at 250 MiB. The current adapter fails
closed for MP4 finalization unless an approved trusted probe supplies dimensions and duration.
`Append Video` is not part of the approved baseline.

## Environment

See `.env.example` for placeholder names. Never commit real credentials or copy secret values into
workspace-local runtime data. Staging/production credentials must come from the approved secret
manager.

## Local migration

Use only an isolated loopback, non-5432, `*_test` database:

```powershell
$env:EVIDENCE_DATABASE_URI='postgresql+psycopg://...@127.0.0.1:55432/..._test'
.\.venv\Scripts\python.exe -m alembic -c services/evidence-service/alembic.ini upgrade head
```

Migration downgrade/reset is destructive and requires explicit approval before execution.

## Tests and quality

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/evidence-service/tests
.\.venv\Scripts\python.exe -m mypy services/evidence-service/src services/evidence-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Tests use synthetic UUIDs and generated media headers only. Never add real student/staff data,
camera media, face crops, ANSVIS payloads, credentials, object locators, or signed URLs to fixtures.

## Logs and metrics

Logs are allowlisted to operational fields such as request/correlation ID, state, media kind and
stable error code. Forbidden fields include object keys, provider versions, bucket names, signed
URLs, upload form fields, hashes tied to real objects, names, biometric payloads, tokens and
credentials.

Required operational counters cover upload/finalization/rejection, authorization allow/deny,
signed-URL issuance failure, reconciliation mismatch, deletion failure and pending-state age.

### Capacity record and alert

The issue worst case is reproduced in code: `1,428,000 events/day × 200,000 bytes = 285.6 GB/day`
when every event has evidence. Expected daily media is:

`285.6 GB/day × approved attachment ratio`

The expected ratio and warning threshold deliberately have no defaults. Pilot/owner approval must
provide `EVIDENCE_EXPECTED_ATTACHMENT_RATIO` and
`EVIDENCE_ATTACHMENT_RATIO_ALERT_THRESHOLD`; startup validation requires the threshold to be
strictly above the expected ratio. `evidence_attachment_ratio_events_total{outcome="attached"|`
`"unattached"}` supplies the bounded numerator/denominator. Alert evaluation waits for the approved
minimum event window. Production activation remains blocked until these values and the #69 TTL
matrix are approved and feed #96 sizing.

## Recovery and rollback

- A database commit always precedes issuing an upload form; if URL creation fails, the object stays
  `pending_upload` for safe retry/reconciliation.
- Finalization verifies exact object version, SHA-256 and ownership before `quarantined`; a clean
  scan is required before `available`.
- Reconciliation compares encrypted-locator output to exact object version, size, content type and
  checksum. Missing/mismatched objects become `missing` and remain inaccessible.
- Deletion first commits `delete_pending` with approved reason/job/request correlation. Legal hold
  blocks this transition. A storage failure remains retryable and emits `EVIDENCE_DELETE_FAILED`;
  physical database rows are never deleted.
- Roll back application code before schema only. Drain uploads, stop the service, verify no
  `pending_upload`, `quarantined`, or `delete_pending` records, preserve the private bucket, and
  back up metadata before Alembic downgrade. Downgrade drops only the `evidence` schema and requires
  explicit destructive approval.
- Never compensate a PostgreSQL failure by blindly deleting an object. Reconcile by opaque key and
  exact version, then record the stable outcome in the audit outbox.
