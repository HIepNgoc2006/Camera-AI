# Baseline quality gates

The repository exposes one stable Python entry point for checks that exist today. It covers the API
Gateway, Identity Service, School Service, Audit Log Service, Consent Service, Camera Registry Service,
ANSVIS Adapter, shared time-policy contract, and ANSVIS HTTP Trigger event contract but does not claim
Web or Mobile commands before those projects are scaffolded.

## Local setup

Use Python 3.12 or newer and an isolated virtual environment. The dependency file pins the exact
quality-tool versions used by CI.

```powershell
rtk python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements-quality.txt
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/api-gateway[test]"
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/identity-service[test]"
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/school-service[test]"
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/audit-log-service[test]"
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/consent-service[test]"
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/camera-registry-service[test]"
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/ansvis-adapter[test]"
```

Do not install from a private index that requires credentials on the command line. The virtual
environment is ignored by Git and must not contain project secrets or real data fixtures.

Direct runtime and test dependencies, their source repositories, SPDX license identifiers, and
approved exceptions are recorded in [open-source-dependencies.md](open-source-dependencies.md).
Third-party software always retains its own license; it must never be described as project-owned
MIT code.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts/quality.py repository
.\.venv\Scripts\python.exe scripts/quality.py foundation
.\.venv\Scripts\python.exe scripts/quality.py compose
.\.venv\Scripts\python.exe scripts/quality.py fixtures
.\.venv\Scripts\python.exe scripts/quality.py time-policy
.\.venv\Scripts\python.exe scripts/quality.py authorization-catalog
.\.venv\Scripts\python.exe scripts/quality.py api-contract
.\.venv\Scripts\python.exe scripts/quality.py ansvis-contract
.\.venv\Scripts\python.exe scripts/quality.py abuse-protection-policy
.\.venv\Scripts\python.exe scripts/quality.py lint
.\.venv\Scripts\python.exe scripts/quality.py typecheck
.\.venv\Scripts\python.exe scripts/quality.py unit
.\.venv\Scripts\python.exe scripts/quality.py all
```

`all` is the required pre-PR and CI command. It stops at the first failing gate and returns that
non-zero exit status. The unit suite contains a synthetic negative test proving failure propagation;
it uses no customer, student, biometric, camera, event, or credential data.

The current gates cover tracked-path safety, repository structure/local links/ignore/defaults,
static Docker Compose safety, synthetic fixture/seed safety, versioned UTC/IANA/drift/replay policy,
versioned API/error/authorization/rate-limit contracts, versioned ANSVIS HTTP Trigger
schema/auth/replay/idempotency/ACK behavior, sanitized cross-system abuse threat model and inherited
limit/metric/issue-owner drift checks, Python lint/format, strict type checking,
repository-script tests, and backend service unit, integration, and contract tests.
The `compose` gate requires Docker Compose but does not start, stop, reset, or delete containers. Add
Web and Mobile lint/typecheck/test commands only when each app scaffold exists.

## CI behavior

`.github/workflows/quality.yml` runs on pull requests, pushes to `main`, and manual dispatch. It uses
read-only repository permission, commit-pinned official actions, Python 3.12, and the pinned tool
versions in `requirements-quality.txt` and each service `pyproject.toml`. Any lint, format, type,
repository-policy, or test failure fails the job. CI requires no production credential, `.env`, or
real fixture. Database integration uses only the CI-owned loopback PostgreSQL service with fake opaque
identifiers.
