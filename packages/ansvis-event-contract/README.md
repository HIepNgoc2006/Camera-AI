# ANSVIS HTTP Trigger contract

This package is the machine-readable V1 boundary for sanitized machine-to-machine ANSVIS events. It
does not implement a production route, database migration, queue, media workflow, Web feature or AI
model pipeline.

## Artifacts

- `http-trigger-request-v1.schema.json`: strict ingress envelope; unknown fields are rejected.
- `canonical-event-v1.schema.json`: vendor-independent normalized event shape.
- `http-trigger-response-v1.schema.json`: durable ACK, duplicate ACK and stable masked error shapes.
- `http-trigger-policy-v1.json`: source authentication, time/replay, rate, idempotency and processing
  order.

The schemas use JSON Schema Draft 2020-12. The policy is versioned independently because changing a
limit, authentication profile, idempotency projection or error meaning can affect deployed producers.

## V1 request boundary

`POST /integration/ansvis/events` accepts only `application/json` with a maximum body size of 64 KiB.
The body carries source/event identity, tenant/school references, camera/task references, event time,
correlation ID and allowlisted attributes. Media, base64, camera addresses, raw vendor payloads,
credentials and unknown attributes are rejected.

ANSVIS documents `EventID` and `CameraID` as integers, but the custom payload may serialize external
identifiers as either an I-JSON safe integer or an opaque string. The canonical event converts both to
strings. A `null` `source_event_id` is allowed only for a controlled legacy/fallback path with all
versioned fallback inputs present; normal Fully Custom payloads must insert `!EventID!`.

`source_namespace`, tenant/school references and task reference are static values configured for the
registered trigger/task; `EventID`, `EventTime` and `CameraID` use ANSVIS dynamic variables. The
receiver derives the authoritative tenant/source mapping from verified authentication and the Camera
Registry instead of trusting body references alone.

## Authentication and replay

ANSVIS documents a `Login Required` flow: it calls a configured login endpoint, extracts the returned
token and attaches it to the event request through the `Authorization` header. V1 therefore uses the
compatible `ansvis-login-bearer-v1` profile over HTTPS, not an undocumented per-request custom-HMAC
header. Each source uses a dedicated least-privilege credential held outside this contract. The
receiver accepts only a cryptographically verified or actively introspected, revocable token with a
trusted issuer, the `camera-ai-ansvis-ingestion` audience, a registered source subject, and a maximum
five-minute lifetime. Token values and login credentials never appear in fixtures, logs or responses.

The verified token subject is mapped to a registered source and must match `source_namespace` in the
body. `event_time` is the replay timestamp and normal `source_event_id`/ANSVIS `EventID` is the replay
nonce. Both are checked under `time_policy_v1`; a durable existing receipt yields the stable duplicate
response while a conflicting reuse is rejected. A critical receiver-clock state fails closed. The
controlled null-ID fallback is adapter-only and uses a keyed, versioned server-side derivation; it is
not the normal ANSVIS configuration.

## Idempotency and durable ACK

The primary identity is `(tenant_ref, source_namespace, source_event_id)`. If the event ID is `null`,
the receiver derives a keyed fallback identity from the exact fields listed in the policy and a
one-second normalized event-time bucket. The fallback is never a public/business identifier.

Canonical fingerprinting uses `camera_ai_canonical_json_v1`: recursively sorted ASCII contract keys,
UTF-8 JSON without whitespace, strict finite numbers, normalized UTC time and normalized external-ID
strings. `correlation_id` is excluded so a transport retry may use a new correlation ID. Identical
identity plus identical fingerprint is a stable duplicate; identical identity plus different content
is rejected and quarantined. Only a committed inbox/receipt may produce an accepted or duplicate ACK.

This work item defines the contract only. The Event Ingestion implementation must enforce the unique
constraint, transaction, quarantine and commit-before-ACK behavior in PostgreSQL.

## Stable responses

- New durable receipt: HTTP `202`, outcome `accepted`.
- Identical durable duplicate: HTTP `200`, outcome `duplicate` and the existing receipt reference.
- Identity conflict/replay: HTTP `409`, masked stable error.
- Invalid schema/auth/content/size/rate/time or unavailable durable store: the status and stable code
  come from the policy; rejected values are never echoed.

Errors remain exactly `{error_code,message,request_id}`. Success responses expose only opaque receipt,
request and correlation identifiers.

## Compatibility and references

V1 changes should be additive. Removing/renaming fields, widening data collection, changing the
authentication profile, changing idempotency semantics or reinterpreting an error requires a new
contract/policy version and migration window. A production endpoint must also align with Issue #59
before activation.

Primary references:

- ANSVIS HTTP Event Trigger: <https://doc.anscenter.com.au/docs/ANSVIS/Advanced-Guides/Event-Trigger/HTTP/>
- JSON Schema Draft 2020-12: <https://json-schema.org/draft/2020-12/json-schema-core>
- OAuth 2.0 Bearer Token Usage: <https://www.rfc-editor.org/rfc/rfc6750>
- HMAC (server-side fallback identity only): <https://www.rfc-editor.org/rfc/rfc2104>
- RFC 3339 time profile: <https://www.rfc-editor.org/rfc/rfc3339>

No third-party runtime package is added by this contract. The checker uses only Python's standard
library and existing project time-policy code.

## Verification

The sanitized contract matrix contains 43 deterministic cases. It covers all nine allowlisted event
types and rejects invalid schema/version/type, replay or future skew, unsafe media/base64 fields,
invalid authentication, oversize input and idempotency conflicts. Adapter contract tests execute the
shared schema cases through the real application service and idempotency derivation boundary; fixture
safety checks run separately.

Run:

```powershell
.\.venv\Scripts\python.exe scripts/quality.py ansvis-contract
.\.venv\Scripts\python.exe scripts/quality.py fixtures
.\.venv\Scripts\python.exe scripts/quality.py all
```
