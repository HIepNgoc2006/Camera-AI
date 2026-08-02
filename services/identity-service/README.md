# Identity Service

Internal Identity boundary for users, roles, credentials, MFA factors, sessions, refresh-token
families, and minimized authentication audit intents. Issue #137 adds the authentication runtime on
top of the policy/domain baseline from Issue #12.

Web and Mobile clients must never call this service directly. External identity requests enter
through API Gateway. The service expects an opaque gateway-derived `X-Client-Source` for login
throttling; direct public exposure or trusting a client-supplied value is forbidden.

## API

`GET /healthz` returns process status and the request correlation ID without dependency, build,
host, account, or configuration details:

```json
{
  "status": "ok",
  "request_id": "req_0123456789abcdef0123456789abcdef"
}
```

The service accepts exactly one safe `X-Request-ID` using the same 1-64 ASCII-character policy as
API Gateway. Missing, duplicate, malformed, or oversized values are replaced. Public errors use
only `error_code`, `message`, and `request_id`; exception messages and stack traces are not returned.

Authentication routes:

| Route | Authentication/permission | Audit intent |
|---|---|---|
| `POST /api/v1/auth/login` | Gateway context; password; TOTP for `admin`/`bgh` | `AUTH_LOGIN_SUCCEEDED` or `AUTH_LOGIN_FAILED` |
| `POST /api/v1/auth/refresh` | Active, unrotated refresh token inside both expiry boundaries | `SESSION_REVOKED` on replay |
| `POST /api/v1/auth/logout` | Active bearer session | `SESSION_REVOKED` |
| `POST /api/v1/auth/logout-all` | Active bearer session; own user only | `SESSION_REVOKED` |
| `POST /api/v1/auth/session/snapshot` | Active bearer session through Gateway | None; returns minimized authoritative expiry/binding metadata |
| `POST /api/v1/auth/mfa/enroll` | Active bearer; current TOTP proof | `MFA_CHANGED` |
| `POST /api/v1/auth/sessions/{session_id}/revoke` | MFA-verified `admin` | `SESSION_REVOKED` |

MFA enrollment accepts a secret only over the protected request channel and returns an opaque factor
ID, never the secret or provisioning URI. Initial MFA provisioning for an account that cannot yet
obtain a session must use an approved trusted administrative workflow; production provisioning is
outside Issue #137.

## Domain and safe read schemas

The framework-free domain package models only the approved identity metadata:

- user ID, tenant ID, normalized non-person-name username, relationship reference, and status;
- role scope/code/name/status and permission resource/action flags;
- scoped role assignment, grant actor, validity interval, and revocation time;
- session ID, owner, expiry, last-seen, and revocation metadata.

Credential material remains absent from general read DTOs. Read DTOs must not contain password,
password hash,
refresh/access token, token hash, ciphertext, MFA secret/reference, recovery code, device
fingerprint, IP address, raw user agent, or provider credential fields. Adding any of these requires
a dedicated storage/transport threat review and must never make them client-facing.

## Database and events

The Alembic chain owns only schema `identity`. Its first migration creates `users`, `credentials`, `roles`,
`user_role_assignments`, `sessions`, `refresh_tokens`, `mfa_factors`, and `audit_outbox`. Other
services must not query this schema. Passwords use Argon2id hashes, refresh tokens use one-way
SHA-256 hashes over purpose-bound high-entropy values, login lookup uses a dedicated HMAC key, and
TOTP secrets use ENCV1 with record/tenant/field AAD. No plaintext credential or token is persisted.

The follow-up session-expiry migration adds non-null `last_activity_at` and
`inactivity_expires_at` fields plus a bounded-window constraint. Sessions created before that
contract are backfilled at the closed inactivity boundary and must authenticate again; guessed
activity is never used to preserve them.

Session and refresh mutation plus its audit intent are committed in one PostgreSQL transaction.
Rotated refresh records are retained until credential-retention expiry so replay can revoke the
entire family.

## Password rules

Login verification uses Argon2id and an Argon2id dummy hash for unknown accounts so unknown-user and
wrong-password requests follow the same comparison and public response path. The runtime also
enforces the following control set:

- Never store plaintext or reversible password encryption. Use a unique salt and an approved modern
  password hash; the current baseline is Argon2id with parameters benchmarked for the deployment and
  no weaker than the OWASP minimum. A pepper, if approved, lives in the secret manager, not Git or
  PostgreSQL.
- For password-only authentication, require at least 15 Unicode code points. A shorter minimum of 8
  is permitted only for an approved MFA flow. Permit at least 64 characters, normalize Unicode with
  NFC before hashing, avoid composition rules, and do not force periodic changes without evidence
  of compromise.
- Check new passwords against an approved common/compromised/context-specific blocklist, rate-limit
  failed authentication, and use non-enumerating client errors. Never log password input, hash,
  blocklist match text, or verification exception details.
- Rehash after successful authentication when approved parameters change. Hashing and verification
  must run outside event-loop blocking paths and be protected against resource exhaustion.

References:

- [NIST SP 800-63B password verifier requirements](https://pages.nist.gov/800-63-4/sp800-63b.html)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

## Token and session rules

The runtime uses five-minute, purpose-bound JWT access tokens with an exact algorithm/key ID,
issuer, audience, issued/not-before/expiry checks, bounded clock skew, opaque session/family/token
IDs, tenant binding, and live session-state verification. Signing material is injected from an
approved secret provider; it has no default or value in Git. Refresh tokens are cryptographically
random, only their hashes are stored, and every use rotates the token. Replay of a rotated token
revokes the affected token family and writes a `SESSION_REVOKED` audit intent.

Identity owns a 30-day absolute session lifetime and a 30-minute inactivity lifetime by default.
Both boundaries are exclusive: `now >= expires_at` or `now >= inactivity_expires_at` denies access.
Successful authenticated access and refresh may move `last_activity_at` forward and extend only the
inactivity boundary, capped by the absolute expiry. PostgreSQL updates are conditional and refresh
rotation locks session state before refresh state, so a concurrent expiry or revocation cannot
revive a session or be misreported as token replay. The gateway-only snapshot response is versioned
as `identity_session_snapshot_v1`, uses canonical millisecond UTC instants, and contains only session,
actor, tenant, optional school, MFA state, issue time, and the two expiry instants plus request ID. It never
contains token, cookie, credential, permission, biometric, or evidence data.

Snapshot reads validate live state but do not update activity or either expiry. This preserves the
Web policy rule that display-only warning polls cannot keep a session alive. Only an authenticated
operation recorded as activity or a successful refresh may move the inactivity boundary.

Rollback must not restore the older absolute-only behavior for a live session. Downgrading the
session-expiry migration first revokes every remaining session, then removes the inactivity fields;
operators must expect mandatory reauthentication and must not bypass that step with manual DDL.

Logout, account disablement, password change, role-risk change, suspected compromise, and retention
expiry must revoke applicable sessions. Tokens must never appear in URLs, query strings, logs,
errors, Web unencrypted local storage, fixtures, or documentation. Web transport and Mobile secure
storage require separate approved designs.

Reference: [OWASP OAuth 2.0 Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html).

## Audit, logging, and retention

Credential, MFA, and session changes produce stable audit actions with
opaque IDs and minimized metadata. Audit events never contain passwords, hashes, token values,
ciphertext, secrets, full request metadata, or free-text reasons. Session/credential expiry follows
`RET-CREDENTIAL`; account deactivation and minimized profile disposal follow `RET-PROFILE`.

Runtime logs are allowlisted JSON only: timestamp, severity, service name, environment, stable event,
request ID, status code, stable error code, and exception class name. Request/response bodies,
headers, query strings, usernames, relationship IDs, tokens, credentials, and exception messages are
not serialized.

## Environment and local run

The process reads `APP_ENV` and `LOG_LEVEL`. Alembic additionally requires
`IDENTITY_DATABASE_URI=postgresql+psycopg://...`; its representation is redacted and no dotenv file
is auto-loaded. Runtime database, signing key, login lookup HMAC, ENCV1 provider, and Redis client
are deliberately composed by the trusted local/deployment profile. Missing composition fails
authentication with a stable 503 instead of weakening a control.

From the repository root:

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "packages/audit-producer" -e "packages/crypto-runtime" -e "services/identity-service[test]"
.\.venv\Scripts\python.exe -m alembic -c services/identity-service/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn identity_service.main:app --app-dir services/identity-service/src --host 127.0.0.1 --port 8001 --no-access-log
```

Loopback and disabled Uvicorn access logs are deliberate local defaults. `main:app` is fail-closed
until a trusted profile injects the runtime. Production activation, keys, Redis/PostgreSQL
credentials, TLS/mTLS, and deployment policy remain separate work.

The guarded migration integration test accepts only `postgresql+psycopg` on loopback port `55432`
with the exact database name `Camera_AI_test`; every other target fails before Alembic runs. The
Compose `postgres-test` profile uses a dedicated bridge whose host binding is fixed to `127.0.0.1`.
Redis, RabbitMQ, and MinIO remain on the separate internal-only network. Start and stop the test
database through the guarded project Docker MCP, and never inject the native development,
staging, or production database URI into this test.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/identity-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Tests use fixed synthetic UUIDs and generic labels only. They cover domain invariants, migration
ownership/rollback, non-enumerating failures, Argon2id, refresh rotation/replay, absolute and
inactivity expiry boundaries, monotonic activity updates, the sanitized snapshot contract, logout and
administrative revocation, TOTP/ENCV1 handling, account/source throttle boundaries, limiter
dependency failure, cross-tenant/expired/revoked/clock-skew tokens, forbidden credential fields,
request correlation, sanitized errors, OpenAPI exposure, and log allowlisting.
