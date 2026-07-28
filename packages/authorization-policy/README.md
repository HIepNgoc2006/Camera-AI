# Authorization policy catalog

`permission-catalog-v1.json` is the single implementation catalog for Issue #13. It defines stable
permission codes, resource/action separation, accepted object-scope dimensions, required ABAC
attributes, purpose/consent handling, and the planned M3 API-to-permission mapping.

The catalog is inactive by itself. It grants no role and contains no role-name matching. Identity
Service owns assignments; each owning service supplies a current, bounded `ScopeGrant` and current
resource attributes to `camera_ai_authorization`. Missing catalog versions, attributes, permissions,
scope, purpose, consent, assignment validity, retention, legal-hold resolution, or dependencies deny.

Protected-object denials and missing objects share public code `AUTHZ_DENIED` with HTTP 404. Internal
reason codes may appear only in minimized audit intents. The catalog contains no user, school,
student, guardian, biometric, evidence locator, credential, endpoint, topology, or production value.

The `api_operations` table is the planned M3 inventory consumed later by Issue #59. Its checker
requires every operation to reference a catalog permission and all five API controls: auth scheme,
permission, object scope, audit action, and rate-limit bucket.

Validate locally:

```powershell
rtk .\.venv\Scripts\python.exe scripts/check_authorization_catalog.py
```

Published v1 is immutable. Changes require a new version, compatibility review, synthetic
allowed/denied evidence, security review, and rollback/supersession record.
