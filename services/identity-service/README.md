# Identity Service

Internal Identity boundary for users, roles, permissions, role assignments, session metadata, and
future MFA work. Issue #12 provides a process and domain skeleton only. It does not authenticate a
user, issue a token, persist identity data, or expose a business API.

Web and Mobile clients must never call this service directly. Future external identity routes must
enter through API Gateway and require separately reviewed authentication, authorization, audit,
rate-limit, and object-boundary controls.

## API

`GET /healthz` is the only route. It returns process status and the request correlation ID without
dependency, build, host, account, or configuration details:

```json
{
  "status": "ok",
  "request_id": "req_0123456789abcdef0123456789abcdef"
}
```

The service accepts exactly one safe `X-Request-ID` using the same 1-64 ASCII-character policy as
API Gateway. Missing, duplicate, malformed, or oversized values are replaced. Public errors use
only `error_code`, `message`, and `request_id`; exception messages and stack traces are not returned.

## Domain and safe read schemas

The framework-free domain package models only the approved identity metadata:

- user ID, tenant ID, normalized non-person-name username, relationship reference, and status;
- role scope/code/name/status and permission resource/action flags;
- scoped role assignment, grant actor, validity interval, and revocation time;
- session ID, owner, expiry, last-seen, and revocation metadata.

Credential material is deliberately absent. Read DTOs must not contain password, password hash,
refresh/access token, token hash, ciphertext, MFA secret/reference, recovery code, device
fingerprint, IP address, raw user agent, or provider credential fields. Adding any of these requires
a dedicated storage/transport threat review and must never make them client-facing.

## Database and events

This scaffold owns no physical database schema, migration, repository, cache, queue, or event. The
approved future schema boundary is `identity`; other services must not read it directly. Physical
tables and migrations require their own issue and must implement encryption, retention, audit, and
tenant/object authorization before use.

## Password rules for future implementation

No password is currently accepted or processed. A future credential issue must implement all of the
following as one reviewed control set:

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

## Token and session rules for future implementation

No token is currently issued or stored. Future implementation must use cryptographically random,
purpose-bound tokens; short access-token lifetime; strict issuer/audience/expiry validation; and
refresh-token rotation or approved sender constraint. Only refresh-token hashes may be stored.
Replay of a rotated token revokes the affected token family and produces an audit/security event.

Logout, account disablement, password change, role-risk change, suspected compromise, and retention
expiry must revoke applicable sessions. Tokens must never appear in URLs, query strings, logs,
errors, Web unencrypted local storage, fixtures, or documentation. Web transport and Mobile secure
storage require separate approved designs.

Reference: [OWASP OAuth 2.0 Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html).

## Audit, logging, and retention

Future credential, role, permission, MFA, and session changes require stable audit actions with
opaque IDs and minimized metadata. Audit events never contain passwords, hashes, token values,
ciphertext, secrets, full request metadata, or free-text reasons. Session/credential expiry follows
`RET-CREDENTIAL`; account deactivation and minimized profile disposal follow `RET-PROFILE`.

Runtime logs are allowlisted JSON only: timestamp, severity, service name, environment, stable event,
request ID, status code, stable error code, and exception class name. Request/response bodies,
headers, query strings, usernames, relationship IDs, tokens, credentials, and exception messages are
not serialized.

## Environment and local run

The process reads only `APP_ENV` and `LOG_LEVEL`; invalid values fail startup. It does not auto-load
dotenv files. From the repository root:

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/identity-service[test]"
.\.venv\Scripts\python.exe -m uvicorn identity_service.main:app --app-dir services/identity-service/src --host 127.0.0.1 --port 8001 --no-access-log
```

Loopback and disabled Uvicorn access logs are deliberate local defaults. Production network policy,
TLS/mTLS, service authentication, trusted proxy handling, rate limiting, and observability require
deployment issues; this scaffold claims none of them.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/identity-service/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Tests use fixed synthetic UUIDs and generic labels only. They cover domain invariants, forbidden
credential fields, dependency boundaries, request correlation, sanitized errors, health-only
OpenAPI exposure, production documentation defaults, and log allowlisting.
