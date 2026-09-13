# Open-source dependency policy and inventory

This file records direct runtime, build, test, and repository-quality dependencies plus the
security/compatibility overrides accepted into this inventory for the implemented services and Web
Portal. It is a code-coupled compliance record, not permission to download or add packages.

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
| setuptools | 83.0.0 | Service build backend | https://github.com/pypa/setuptools | MIT | Preferred |
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
| pip-audit | 2.10.1 | Python vulnerability audit | https://github.com/pypa/pip-audit | Apache-2.0 | Recorded security-tool exception |
| Bandit | 1.9.4 | Python SAST | https://github.com/PyCQA/bandit | Apache-2.0 | Recorded security-tool exception |
| OpenGrep standalone | 1.22.0 (`sha256:45bcd584...f62e319`) | Semgrep-compatible Python/TypeScript local-rule SAST | https://github.com/opengrep/opengrep | LGPL-2.1 | Official release binary pinned by SHA-256; remote version check/config and source upload disabled |
| Trivy | 0.70.0 | Filesystem vulnerability/misconfiguration scan | https://github.com/aquasecurity/trivy | Apache-2.0 | Checksum-verified standalone CI/local tool |
| Next.js | 16.3.5 | Web Portal runtime | https://github.com/vercel/next.js | MIT | Exact patched runtime release |
| Vitest | 4.1.11 | Web Portal test runner | https://github.com/vitest-dev/vitest | MIT | Exact patched test release |
| js-yaml | 4.3.2 | Security override for the version used by ESLint tooling | https://github.com/nodeca/js-yaml | MIT | Exact override for fixed release |
| Vite | 8.1.5 | Compatibility override for the Vitest toolchain | https://github.com/vitejs/vite | MIT | Preserves the verified pre-remediation toolchain baseline |
| PostCSS | 8.5.25 | Security override for the version bundled by Next.js | https://github.com/postcss/postcss | MIT | Exact override for fixed release |
| sharp | 0.35.4 | Security override for the optional image runtime bundled by Next.js | https://github.com/lovell/sharp | Apache-2.0 | Exact override for fixed release |

The Web Portal rows from Next.js through sharp were resolved or re-verified during the 2026-09-13
review. Other rows retain their previously recorded values and were not re-resolved by this task.
Service declarations may use compatible ranges, so dependency updates must re-resolve, re-verify
upstream metadata, and update this table in the same implementation change.
