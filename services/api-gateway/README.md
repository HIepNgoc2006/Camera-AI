# API Gateway

FastAPI entry point for external Web/Mobile traffic. Issue #11 provides the safe process baseline;
Issue #137 adds the allowlisted authentication ingress that forwards only approved calls to the
private Identity Service.

## API

`GET /healthz` is unauthenticated and returns only process status plus the request correlation ID:

```json
{
  "status": "ok",
  "request_id": "req_0123456789abcdef0123456789abcdef"
}
```

The gateway accepts one `X-Request-ID` only when it is 1-64 ASCII characters matching
`[A-Za-z0-9][A-Za-z0-9._:-]*`. Missing, duplicated, malformed, or oversized values are replaced with
a generated ID. Every response echoes the accepted/generated ID in `X-Request-ID`.

Errors use this stable public shape and never include stack traces or exception messages:

```json
{
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Resource not found",
  "request_id": "req_0123456789abcdef0123456789abcdef"
}
```

The gateway exposes the Identity Service authentication surface under `/api/v1/auth`: login,
refresh, logout, logout-all, the authoritative session snapshot, MFA enrollment, and administrative session revoke. It derives a
pseudonymous source key from the transport client address and overwrites any caller-supplied
`X-Client-Source`. Only request ID, that source key, optional Authorization, JSON body, and three safe
upstream response headers cross the service boundary. Bodies are capped at 8 KiB and never logged.
The cap is enforced incrementally before buffering each stream chunk. Oversized or invalid,
duplicated, or mismatched Content-Length is rejected with the existing 400 `BAD_REQUEST` response
before forwarding to Identity.

## Events and database

This service consumes and publishes no events and owns no database schema. Its only current service
dependency is the private Identity Service HTTP boundary. Missing upstream composition, invalid
upstream URLs, network failure, or non-loopback plaintext HTTP all fail closed.

## Environment

Copy `.env.example` only when a local launcher needs it. The application reads these non-secret
variables directly and does not auto-load `.env` files:

- `APP_ENV`: `development`, `test`, `staging`, or `production`; production disables interactive API
  documentation.
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.

The Identity upstream is injected by the trusted local/deployment profile; no credentialed URL or
default endpoint is stored in config. Plain HTTP is accepted only for loopback local profiles.
Invalid values fail startup. Do not add secrets, tokens, credentials, RTSP URLs, or customer data.

## Local run

From the repository root, use the workspace `.venv` and workspace-local package cache:

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/api-gateway[test]"
.\.venv\Scripts\python.exe -m uvicorn api_gateway.main:app --app-dir services/api-gateway/src --host 127.0.0.1 --port 8000
```

The service binds to loopback in this example. `main:app` leaves Identity unwired and returns a
stable 503 for authentication until the trusted profile injects the upstream. Deployment exposure,
TLS, trusted proxy handling, CORS, and production service authentication require separate work.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/api-gateway/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Tests use synthetic identifiers only. They cover liveness minimization, request-ID validation,
correlated error envelopes, production documentation defaults, log allowlisting, the OpenAPI
contract, fail-closed upstream behavior, enumeration-safe forwarding, and an in-process local
login/session-snapshot/refresh/logout flow through Gateway and Identity Service.

## Logs and security

Logs are JSON objects built from an allowlist: timestamp, severity, service name, environment,
stable event name, request ID, status code, stable error code, and exception class name when an
unexpected failure occurs. Request/response bodies, headers, query strings, tokens, credentials,
biometric data, raw ANSVIS payloads, and exception messages are never serialized.

The process-level health response proves only that the API process is responsive. Identity runtime
health, authorization, audit delivery, consent enforcement, and object-level policy are separate
checks and are never inferred from `/healthz`.
