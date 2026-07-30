# Sanitized security baseline

> Publication status: minimum implementation baseline; fail closed where a required decision,
> attribute, policy version, consent, dependency, or approval is absent.
>
> Local source authorities (not published in the implementation repository):
> `implementation-planning/planning/security-privacy-plan.md` and
> `implementation-planning/planning/database-and-encryption-plan.md`.
>
> Canonical body SHA-256: `c814d3fb29950e1b2f37ea34d79e5416be248f7a8bfc6779d37a60c6ee1e4cfd`
>
> Hash rule: SHA-256 of the UTF-8 text after the `baseline-body:start` marker, with line endings
> normalized to LF and exactly one trailing LF. The metadata above is excluded.

<!-- baseline-body:start -->

## Status and scope

This document publishes the minimum sanitized controls required for implementation and review. It
does not publish credentials, key material, provider or account identifiers, deployment topology,
private endpoints, production values, personal data, biometric data, evidence locators, or raw
ANSVIS payloads.

Higher sensitivity wins when data could fit more than one class. Authorization, consent, purpose,
retention, audit, and encryption are independent controls; satisfying one does not bypass another.

## Data classification

| Data | Classification | Minimum handling |
|---|---:|---|
| Face image, crop, embedding, or face database | Critical | Valid consent and purpose, encryption, restricted object access, audit, approved retention |
| Student, parent, staff, or class profile | Critical | RBAC plus ABAC, object-level authorization, no real test data |
| Person-linked emotion inference | Critical | Purpose and biometric consent, short TTL, object authorization, audit, no high-impact automatic decision |
| Attendance or staff timekeeping | High | Permission separation, object scope, audit, retention |
| Violation, uniform, or PPE event and evidence | High | Private storage, short-lived grant, view/download/export separation, audit, retention |
| Sanitized ANSVIS event JSON | High | Source authentication, schema and size validation, normalization, masking, idempotency, retention |
| Anonymous aggregate insight | High | Minimum group threshold, anti-reidentification controls, export audit, retention |
| Logs, traces, and errors | Medium/High | Redaction, restricted access, retention; no raw biometric, token, or credential |
| Secret, key, token, license, or credential metadata | Critical | Approved secret manager or credential store, least privilege, rotation, no Git |

Media binary must not be stored in PostgreSQL business tables. Evidence belongs in private object
storage and is exposed only through an authorized, short-lived grant.

## RBAC and ABAC authorization model

RBAC defines candidate permissions; it does not grant unrestricted data access. Every protected
request must also evaluate current ABAC context:

- tenant or school scope;
- object identity and ownership;
- active class, shift, zone, camera, or task assignment as applicable;
- declared purpose and sensitivity;
- consent state for biometric processing;
- retention state and legal-hold resolution;
- assignment validity and required policy/catalog version.

Missing or stale inputs deny. Protected-object denial and not-found responses must not reveal object
existence. The tracked implementation authority is
[`packages/authorization-policy/permission-catalog-v1.json`](../packages/authorization-policy/permission-catalog-v1.json);
role assignments remain owned by the identity boundary and are not inferred from role-name strings.

Sensitive actions are separate permissions. At minimum, implementations must not collapse
`view_metadata`, `view_thumbnail`, `view_original`, `download`, `export`, `correct`, `review`,
`delete_request`, `hold_request`, and `hold_approve` into one broad grant. Administrative and
operational roles do not receive business evidence or decryption access by default. Bulk or critical
disposal requires separation between requester and final approver.

Allowed and denied access, cross-object access, missing attributes, expired assignment, absent or
withdrawn consent, purpose mismatch, retention expiry, and legal hold require synthetic tests.

## Encryption and lookup baseline

Sensitive field encryption uses the tracked `ENCV1` runtime contract:

- AES-256-GCM authenticated encryption;
- a new data-encryption key (DEK) and 96-bit nonce for every encryption operation;
- a versioned envelope containing algorithm metadata, a non-secret logical key identifier, wrapped
  DEK, nonce, ciphertext and tag, and AAD schema;
- associated data binding to service, schema/table/field, immutable record identifier, and tenant
  scope;
- fail-closed behavior for unavailable, disabled, malformed, tampered, or context-mismatched keys
  and envelopes;
- no plaintext fallback and no sensitive material in public errors or logs.

Exact lookup uses `LOOKUP-V1`: full-length HMAC-SHA-256 with a separate lookup key and mandatory
domain separation by purpose, tenant, and normalization version. Ciphertext itself must not be
searched or indexed.

Key roles remain purpose-separated:

| Key role | Required boundary |
|---|---|
| Provider/root control key | Provider control plane only; never used directly for business-field encryption |
| KEK/wrapping key | Wraps ENCV1 DEKs; separated by environment, service, purpose, and sensitivity |
| Per-operation DEK | Plaintext exists only briefly in memory; never reused across operations |
| LOOKUP-V1 HMAC key | Separate from KEK/DEK and scoped to lookup domain |
| Service credential or signing key | Separate from all data keys; prefer short-lived workload identity |
| Recovery control | Restricted, time-bound, dual-controlled recovery or rewrap authorization |

The tracked runtime specification is
[`packages/crypto-runtime/README.md`](../packages/crypto-runtime/README.md). Real provider
provisioning, key material, account mapping, and recovery ceremony are intentionally excluded here.

## Ingestion rate-limit baseline

The ANSVIS HTTP-trigger contract limits each source namespace to 50 sustained requests/second with a
burst allowance of 200 requests. Exceeding the bucket returns HTTP 429. A rate-limit dependency
failure must fail closed rather than silently disabling enforcement.

The tracked authority is
[`packages/ansvis-event-contract/http-trigger-policy-v1.json`](../packages/ansvis-event-contract/http-trigger-policy-v1.json).
Changing these limits requires a new or superseding contract version plus load, abuse, and rollback
review.

## Retention and disposal baseline

Retention begins from the canonical trigger, not merely the insert time. Expiry first removes access;
disposal then deletes the exact object/version or anonymizes the subject link according to the active
policy. A legal hold blocks disposal but does not independently grant access.

| Data or artifact | TTL | Canonical trigger | Terminal rule |
|---|---:|---|---|
| Attendance event JSON | 3 years | `session_closed_at` | Remove subject link; retain only independently justified non-reidentifiable aggregate |
| Attendance retained evidence | 180 days | `session_closed_at` | Delete exact object version/link; retain tombstone and audit |
| Staff timekeeping event JSON | 5 years | `shift_closed_at` | Remove subject link or retain-restricted only under active HR/legal policy |
| Staff timekeeping retained evidence | 1 year | `shift_closed_at` | Delete exact object version/link |
| Unreviewed suspected violation | 30 days | `event_ended_at` | Delete event/evidence unless held; never auto-confirm |
| Rejected violation evidence | 15 days | `rejected_at` | Delete media; retain minimized result, reason code, and deletion audit |
| Confirmed violation and evidence | 1 year | `case_closed_at` | Delete or anonymize under active policy; time-bounded appeal/hold may block disposal |
| Uniform or PPE JSON | 1 year | `case_closed_at` | Remove subject link; aggregate only when non-reidentifiable |
| Uniform or PPE evidence | 180 days | `case_closed_at` | Delete exact object version/link |
| Person-linked emotion JSON | 90 days | `event_ended_at` | Delete or anonymize subject link; no convenience history |
| Temporary emotion image | 24 hours | `review_completed_at` or `event_ended_at` | Delete; do not promote by default |
| Unknown-face representative | Maximum 7 days | `captured_at` | Default is no storage; approved investigation exception must expire |
| Attendance/timekeeping intermediate | Session/shift close + 24 hours | `session_closed_at` or `shift_closed_at` | Delete after retained evidence is finalized and checksum-verified |
| Untriggered behavior rolling buffer | 30-60 seconds | Rolling capture time | Automatically overwrite or delete |
| Selected temporary behavior image | Maximum 72 hours | `event_ended_at` | Delete after selection/promotion; alert and fail closed when overdue |
| Report export artifact | 7 days | `export_created_at` | Revoke grant and delete exact artifact; retain minimized export audit |
| Sensitive access/deletion audit | 5 years | `recorded_at` | Verify chain/checkpoint before approved partition retirement |

Signed evidence GET grants default to 60 seconds and have a hard maximum of 300 seconds. Business
cutoff uses the versioned `Asia/Ho_Chi_Minh` timezone; persistence and comparison use UTC.

These periods become active only when the exact trigger, action, owner, policy version, effective
date, and required privacy/legal/security approvals exist. Until then, production activation is
blocked; the numbers in this document do not authorize an agent to invent or enable a policy.

## Audit baseline

Every sensitive view, denial, change, correction, review, consent action, permission change,
evidence grant, download, export, retention action, legal-hold change, key lifecycle action, and
backup/restore action emits a minimized, structured audit event. Audit records use opaque
identifiers and counts; they must not contain secret values, plaintext sensitive fields, raw media,
face embeddings, access tokens, credentialed URLs, or full raw event payloads.

The tracked action-policy registry is
[`services/audit-log-service/src/audit_log_service/domain/policies.py`](../services/audit-log-service/src/audit_log_service/domain/policies.py).
It validates approved actions, publishers, resource types, results, purpose requirements, controlled
fields, references, counts, and policy versions and rejects unknown combinations. Producer shape and
redaction constraints are defined by
[`packages/audit-producer`](../packages/audit-producer/).

## Verification and change control

Before merge, changes governed by this baseline require the relevant subset of:

- authorization allowed/denied and object-boundary tests;
- consent and purpose failure tests;
- encryption tamper, AAD mismatch, key-unavailable, rotation, and lookup-domain tests;
- ingestion authentication, replay, idempotency, size, and rate-limit tests;
- retention trigger, deny-before-dispose, hold, retry, idempotency, and tombstone tests;
- audit action-registry, redaction, integrity, and access tests;
- lint, typecheck, unit/integration/contract tests, secret scan, and sanitized-fixture scan.

Any baseline change requires approval in the local source authorities, a minimal sanitized update
here, canonical body hash regeneration, dependent-Issue review, and an implementation/security
review. This document never overrides a stricter approved control.
