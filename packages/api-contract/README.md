# Protected API contract

This package is the inactive, versioned M3 contract shared by API Gateway, Web, and Mobile. It defines
34 planned operations but does not register routes, start a service, access a database, or authorize
production traffic.

## Artifacts

- `openapi-v1.json`: OpenAPI 3.1 contract under `/api/v1`, with sanitized opaque examples.
- `error-codes-v1.json`: stable error-code registry with HTTP status, retryability, exposure, safe
  message, and redaction behavior.
- `api-contract-policy-v1.json`: route, versioning, pagination, idempotency, request-ID, compatibility,
  deprecation, and rate-limit rules.
- `review-record-v1.json`: security/backend/Web/Mobile review evidence and explicit release limits.

Every operation maps exactly to `permission-catalog-v1.json` and declares its authentication scheme,
permission, object scope, audit action, and rate-limit bucket. Protected missing-object and denied
responses are intentionally indistinguishable. Sensitive request or response fields, raw ANSVIS
payloads, media locators, credentials, biometric data, and real identifiers are outside this
contract.

## Compatibility rules

Published v1 fields and operation semantics are additive-only. A removal, rename, type narrowing,
required-field addition, permission change, object-scope change, audit change, or rate-limit
tightening requires a new contract version and security/backend/Web/Mobile review. Deprecation must
name a replacement and retain the documented minimum notice window.

List operations use opaque cursor pagination and bounded `limit`; filters are explicit query
parameters. Mutating operations require `Idempotency-Key`. Clients may send `X-Request-ID`, and the
gateway must return the effective request ID in both success and error responses. The public error
shape is exactly:

```json
{
  "error_code": "VALIDATION_FAILED",
  "message": "The request failed validation.",
  "request_id": "req_synthetic_0001"
}
```

Rate limits are policy buckets rather than runtime activation. ANSVIS ingestion is fixed at 50
requests/second sustained with burst 200; login is 5/10; export is 1/3. A limited response is HTTP
429 with `Retry-After`. Runtime configuration may be more conservative only after compatibility and
security review.

## Verification

```powershell
rtk .\.venv\Scripts\python.exe scripts/check_authorization_catalog.py
rtk .\.venv\Scripts\python.exe scripts/check_api_contract.py
rtk .\.venv\Scripts\python.exe scripts/quality.py api-contract
```

The checker cross-validates all operations against the authorization catalog and audit taxonomy,
requires seeded service error codes in the registry, rejects sensitive schema properties, and
generates an in-memory TypeScript interface as a deterministic consumer smoke test. It writes no
generated client or runtime configuration.

Rollout requires implementation behind API Gateway, backend authorization and audit enforcement,
consumer integration tests, security review, and human UAT. Rollback means keeping runtime
activation disabled or routing back to the previous independently reviewed contract; never edit a
published contract in place.
