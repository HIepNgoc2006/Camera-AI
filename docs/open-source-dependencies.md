# Open-source dependency policy and inventory

This file records the direct Python runtime, build, test, and repository-quality dependencies
currently declared by the implemented services. It is a code-coupled compliance record, not
permission to download or add packages.

## Policy

- Prefer dependencies licensed under the MIT License when adding new software.
- Record the package name, resolved version, canonical source, and SPDX license identifier before
  acceptance. Preserve the dependency's notices and license terms.
- A third-party dependency keeps its actual license. Do not relabel BSD, LGPL, or other third-party
  code as MIT.
- A new non-MIT dependency requires an explicit documented exception and compatibility/security
  review. The Apache-2.0, BSD-3-Clause, and LGPL-3.0-only packages below are the currently recorded
  exceptions.
- Project-owned source is not automatically MIT-licensed. A root `LICENSE` may be added only after
  the copyright holder and publication decision are explicitly approved.
- Version or dependency changes must update this inventory and pass the repository quality gates,
  `pip check`, and the available vulnerability/license checks. Missing scanners must be reported;
  they must not be installed globally or outside the workspace.

## Direct dependency inventory

| Package | Resolved version | Used by | Canonical source | SPDX license | Status |
|---|---:|---|---|---|---|
| setuptools | 80.9.0 | Service build backend | https://github.com/pypa/setuptools | MIT | Preferred |
| Alembic | 1.18.5 | Audit, Consent, School | https://github.com/sqlalchemy/alembic | MIT | Preferred |
| Psycopg | 3.3.4 | Audit, Consent, School | https://github.com/psycopg/psycopg | LGPL-3.0-only | Recorded PostgreSQL-driver exception |
| psycopg-binary | 3.3.4 | Binary extra for Psycopg | https://github.com/psycopg/psycopg | LGPL-3.0-only | Same PostgreSQL-driver exception |
| Pydantic | 2.13.4 | API Gateway, ANSVIS Adapter, Audit, Consent, Identity | https://github.com/pydantic/pydantic | MIT | Preferred |
| SQLAlchemy | 2.0.51 | Audit, Consent, School | https://github.com/sqlalchemy/sqlalchemy | MIT | Preferred |
| FastAPI | 0.139.0 | API Gateway, ANSVIS Adapter, Identity | https://github.com/fastapi/fastapi | MIT | Preferred |
| Uvicorn | 0.51.0 | API Gateway, ANSVIS Adapter, Identity | https://github.com/Kludex/uvicorn | BSD-3-Clause | Recorded runtime-server exception |
| pytest | 9.1.1 | Implemented service test suites | https://github.com/pytest-dev/pytest | MIT | Preferred |
| pytest-asyncio | 1.4.0 | Repository async test support | https://github.com/pytest-dev/pytest-asyncio | Apache-2.0 | Recorded test-tool exception |
| httpx2 | 2.7.0 | API Gateway, ANSVIS Adapter and Identity tests | https://github.com/pydantic/httpx2 | BSD-3-Clause | Recorded test-client exception |
| mypy | 2.3.0 | Repository type checking | https://github.com/python/mypy | MIT | Preferred |
| Ruff | 0.15.21 | Repository lint and format checking | https://github.com/astral-sh/ruff | MIT | Preferred |

Versions are the environment resolved during the 2026-07-19 review. Service declarations may use
compatible ranges, so dependency updates must re-resolve, re-verify upstream metadata, and update
this table in the same implementation change.
