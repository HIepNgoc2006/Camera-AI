# Report and Export Service

## Purpose

This service produces authorized dashboard aggregates and controlled export jobs from synthetic or
canonical business-service DTOs. It never reads another service schema. Source adapters must apply
object-level SQL filters before rows are fetched. View permission does not imply export permission.

## Security and data

Report/export data is High and becomes Critical when it contains student, parent, staff, biometric,
or evidence-linked fields. Production activation defaults to blocked until the minimum cohort size,
Privacy/Legal, Security/Ops, and business-owner approvals are supplied. Withdrawn-consent subjects
and expired records are excluded from new results. Legal hold prevents disposal but grants no
visibility.

The `reporting` schema owns:

- `report_aggregates`;
- `report_exports`;
- `audit_outbox`.

Stored export parameters are reduced to a SHA-256 scope fingerprint. Artifact references are opaque
UUIDs; object keys, signed URLs, exported content, subject values, and evidence locators are never
stored in PostgreSQL, audit, queue messages, metrics, or logs.

## Contracts

- `run_report`: requires `report.view_metadata`; returns aggregate cells suppressed when the approved
  cohort threshold is unavailable or unmet.
- `request_export`: requires `report.export`, an allowlisted reason, and approval for cross-class or
  cross-school scope.
- `generate_export`: re-queries current authorized rows, writes a private artifact, and records only
  the opaque artifact reference and row count.
- `download_export`: re-authorizes at delivery time and returns a signed GET with 60-second default
  and 300-second hard maximum.
- `expire_export`: denies before disposal and deletes the exact private artifact. Artifacts expire
  after seven days; source legal hold does not extend them.

Heavy work is queued through a bounded port. Per-actor concurrency and queue limits return
`REPORT_EXPORT_QUOTA_EXCEEDED` with `Retry-After`. Production queue thresholds remain governed by
Issue #35.

## Environment

`.env.example` contains placeholders only. The minimum cohort size has no default. Real credentials
must come from the approved secret manager; no production bucket or credential is provisioned here.

## Local migration

Use only an isolated loopback, non-5432, `*_test` database. Downgrade/reset is destructive and needs
explicit approval.

```powershell
$env:REPORT_DATABASE_URI='postgresql+psycopg://...@127.0.0.1:55432/..._test'
.\.venv\Scripts\python.exe -m alembic -c services/report-service/alembic.ini upgrade head
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/report-service/tests
.\.venv\Scripts\python.exe -m mypy services/report-service/src services/report-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Fixtures use generated UUIDs and fake counts only. Never add real people, biometric data, media,
evidence, raw ANSVIS payloads, credentials, export files, or signed URLs.

## Logs, metrics, recovery, and rollback

Logs allowlist request/correlation ID, stable action/outcome, row count, state, and error code. They
exclude report parameters, subject IDs, evidence IDs, artifact references, URLs, content, and
credentials. Metrics use bounded outcomes only.

On generation failure the job stays retryable without an artifact grant. Authorization is checked
again before generation and download. Expired artifacts are denied even if asynchronous deletion
fails. Roll back application code before schema, disable the worker, preserve private artifacts, and
reconcile opaque artifact references before any separately approved downgrade.
