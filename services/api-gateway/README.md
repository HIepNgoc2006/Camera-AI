# API Gateway

FastAPI entry point for external Web/Mobile traffic. Issue #11 provides only the safe process
skeleton: liveness, request correlation, structured allowlist logging, a stable error envelope, and
an empty versioned router. It does not implement business APIs or process customer data.

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

`/api/v1` is reserved as the versioned business-router boundary. This scaffold deliberately adds no
route below it.

## Events and database

This service currently consumes and publishes no events and owns no database schema. It does not
connect to PostgreSQL, RabbitMQ, object storage, cameras, ANSVIS, or another service.

## Environment

Copy `.env.example` only when a local launcher needs it. The application reads these non-secret
variables directly and does not auto-load `.env` files:

- `APP_ENV`: `development`, `test`, `staging`, or `production`; production disables interactive API
  documentation.
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.

Invalid values fail startup. Do not add secrets, tokens, credentials, RTSP URLs, or customer data.

## Local run

From the repository root, use the workspace `.venv` and workspace-local package cache:

```powershell
$env:PIP_CACHE_DIR = 'D:\WORKSAPCE\Camera AI\.local\cache\pip'
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/api-gateway[test]"
.\.venv\Scripts\python.exe -m uvicorn api_gateway.main:app --app-dir services/api-gateway/src --host 127.0.0.1 --port 8000
```

The service binds to loopback in this example. Deployment exposure, TLS, trusted proxy handling,
CORS, authentication, rate limiting, and upstream routing require separate approved work.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q services/api-gateway/tests
.\.venv\Scripts\python.exe scripts/quality.py all
```

Tests use synthetic identifiers only. They cover liveness minimization, request-ID validation,
correlated error envelopes, production documentation defaults, log allowlisting, and the OpenAPI
contract.

## Logs and security

Logs are JSON objects built from an allowlist: timestamp, severity, service name, environment,
stable event name, request ID, status code, stable error code, and exception class name when an
unexpected failure occurs. Request/response bodies, headers, query strings, tokens, credentials,
biometric data, raw ANSVIS payloads, and exception messages are never serialized.

The process-level health response proves only that the API process is responsive. Authentication,
authorization, audit persistence, consent enforcement, and object-level policy remain mandatory for
future sensitive routes and are not claimed by this scaffold.
