# Web BFF session and cookie security runbook

Policy version: `web_bff_session_policy_v1`
Runtime status: inactive and fail-closed

The machine-readable authority is
[`packages/web-bff-session-policy/web-bff-session-policy-v1.json`](../../packages/web-bff-session-policy/web-bff-session-policy-v1.json).
This runbook explains how Issue #70 may implement and verify that contract. It does not authorize a
production session, secret, cookie, endpoint, provider, hosting change, or deployment.

## Boundary and custody

The browser talks only to the same-origin Web BFF. The BFF calls backend APIs only through API
Gateway. Identity Service remains authoritative for credential/MFA verification, token material,
refresh rotation, session/family revocation, and expiry. Backend resource owners remain authoritative
for tenant, school, object, purpose, consent, and audit decisions.

Access and refresh material stays in the BFF/Identity server boundary. It must never enter browser
storage, script-readable cookies, URLs, HTML, analytics, client-authored authorization state, logs,
traces, audit payloads, errors, screenshots, or test fixtures. Cookie presence is not authorization.

## Cookie and transport

The session cookie is opaque, `HttpOnly`, `SameSite=Strict`, host-only, and path `/`. Secure
non-loopback environments use a server-configured name with the `__Host-` prefix. An explicitly
detected loopback plain-HTTP development profile must use a separate non-production server-configured
name because the secure prefix contract cannot be weakened. `Secure` is mandatory for production and
every non-loopback environment; a non-loopback downgrade is rejected. Cookie expiry comes only from
authoritative Identity metadata and the Web layer cannot extend it.

No cookie value, secret, or environment-specific name belongs in Git or this runbook. A deployment
profile must supply those values through the approved secret/configuration boundary and must fail
closed when absent.

## CSRF, origin, and redirects

Every state-changing `POST`, `PUT`, `PATCH`, or `DELETE` request requires an exact same-origin match
from a server-side allowlist and a session-bound anti-CSRF value validated by the BFF. Null, wildcard,
missing, or cross-origin values deny the request. The anti-CSRF value may be submitted in an approved
header or form field, but never in a URL, browser storage, log, trace, audit record, or error.

Redirects come from server-side route codes. Absolute URLs, scheme-relative targets, backslashes,
encoded separators/dot segments, and client-supplied return targets are rejected. `/login` is the
fail-closed fallback.

## Session states and expiry

The Web login flow recognizes exactly: `unauthenticated`, `mfa_required`, `mfa_failed`,
`authenticated`, `expired`, `revoked`, `unavailable`, and `malformed`. Only an exact
`web_bff_session_policy_v1` authenticated snapshot with `rbac_policy_v1`, server-authoritative
actor/tenant/school/MFA fields, and valid UTC expiry metadata may reach the existing route/action
guard.

Identity Service owns absolute and inactivity expiry. A named approved runtime profile may own the
warning timestamp, but the Web policy contains no copied duration. The boundary is exclusive:
`now >= absoluteExpiresAt` or `now >= inactivityExpiresAt` is expired. A warning is display-only; it
never refreshes or extends a session. Missing, invalid, reordered, stale, or client-augmented metadata
fails closed.

Identity now exposes the gateway-only `POST /api/v1/auth/session/snapshot` contract versioned as
`identity_session_snapshot_v1`. It enforces the absolute and inactivity boundaries before returning
canonical `absoluteExpiresAt` and `inactivityExpiresAt` values, and successful activity can extend
only the inactivity value up to the absolute cap. Issue #70 must map this minimized Identity response
into the exact Web snapshot and must not derive a second lifetime in Web code. Only the display-only
warning timestamp may come from a separately named and approved runtime profile.

MFA failures use stable, non-enumerating UI state. `unavailable` and `malformed` never reuse a cached
allow. Backend object authorization still runs for every sensitive request after route access.

## Refresh, logout, and revocation

Every refresh rotates the refresh token. Replay of a rotated token revokes its family, clears the
local cookie, and denies access. Dependency failure denies refresh without extending stale state.
Logout revokes the current server session before reporting success; logout-all revokes all current
user sessions. Clearing a browser cookie without confirmed Identity revocation is only a local deny,
not proof that server revocation succeeded.

## Verification and rollback

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe scripts/check_web_bff_session_policy.py
npm --prefix apps/web-portal run quality
.\.venv\Scripts\python.exe scripts/quality.py all
```

The checker must pass the synthetic positive/negative matrix. Web tests must cover exact policy
versions, every state transition, either-expiry boundary, malformed and client-augmented snapshots,
and same-origin redirects. Secret scanning must find no credential/session value.

Rollback is code/config revert to the fail-closed null session seam. Do not roll back by enabling a
readable cookie, browser token storage, plain non-loopback HTTP, relaxed CSRF/origin validation,
longer Web-owned timeout, cached authorization, or direct service access. Production activation needs
Issue #70 completion, an Identity-owned absolute/inactivity snapshot contract, named Security/Ops
approval, an approved cookie/timeout profile, secret-provider wiring, exact-head review, and a
deployment change/rollback record.
