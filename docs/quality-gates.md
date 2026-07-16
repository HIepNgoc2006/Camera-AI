# Baseline quality gates

The repository exposes one stable Python entry point for checks that exist today. It covers the
API Gateway scaffold but does not claim Web or Mobile commands before those projects are scaffolded.

## Local setup

Use Python 3.12 or newer and an isolated virtual environment. The dependency file pins the exact
quality-tool versions used by CI.

```powershell
rtk python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements-quality.txt
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e "services/api-gateway[test]"
```

Do not install from a private index that requires credentials on the command line. The virtual
environment is ignored by Git and must not contain project secrets or real data fixtures.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts/quality.py repository
.\.venv\Scripts\python.exe scripts/quality.py foundation
.\.venv\Scripts\python.exe scripts/quality.py compose
.\.venv\Scripts\python.exe scripts/quality.py fixtures
.\.venv\Scripts\python.exe scripts/quality.py lint
.\.venv\Scripts\python.exe scripts/quality.py typecheck
.\.venv\Scripts\python.exe scripts/quality.py unit
.\.venv\Scripts\python.exe scripts/quality.py all
```

`all` is the required pre-PR and CI command. It stops at the first failing gate and returns that
non-zero exit status. The unit suite contains a synthetic negative test proving failure propagation;
it uses no customer, student, biometric, camera, event, or credential data.

The current gates cover tracked-path safety, repository structure/local links/ignore/defaults,
static Docker Compose safety, synthetic fixture/seed safety, Python lint/format, strict type
checking, repository-script tests, and API Gateway unit/integration/contract tests. The `compose`
gate requires Docker Compose but does not start, stop, reset, or delete containers. Add Web and
Mobile lint/typecheck/test commands only when each app scaffold exists.

## CI behavior

`.github/workflows/quality.yml` runs on pull requests, pushes to `main`, and manual dispatch. It uses
read-only repository permission, commit-pinned official actions, Python 3.12, and the pinned tool
versions in `requirements-quality.txt` and `services/api-gateway/pyproject.toml`. Any lint, format,
type, repository-policy, or test failure fails the job. CI requires no database, production
credential, `.env`, or real fixture.
