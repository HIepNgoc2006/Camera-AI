# Software supply-chain scanning

Issue #112 adds a required pull-request gate for Python and Web dependency vulnerabilities, Python
SAST, and repository filesystem vulnerabilities/misconfiguration. It operates only on source,
manifests, dependency metadata, and synthetic canaries. Real student/staff data, face data, camera
events, evidence, credentials, private indexes, and production endpoints are prohibited.

## Pinned tools and trust boundary

| Gate | Pinned implementation | Pull-request failure condition |
|---|---|---|
| Python dependency audit | pip-audit 2.10.1 over `requirements-security-audit.txt` | Any known vulnerability or audit error (`--strict`) |
| Source SAST | Bandit 1.9.4 plus Semgrep-compatible OpenGrep 1.22.0 standalone binary pinned to SHA-256 `45bcd584...f62e319` | High/Critical policy finding |
| Filesystem | Trivy 0.70.0, immutable release archive with committed SHA-256 | High/Critical vulnerability or misconfiguration |
| Web dependencies | npm audit over the committed Web Portal lockfile | High/Critical vulnerability |

CI installs Python scanners from exact PyPI pins and audits only through PyPI/OSV; npm audit uses the
official npm registry. It downloads OpenGrep v1.22.0 and the fixed Trivy v0.70.0 Linux archive only
from their official GitHub releases, and verifies the committed SHA-256 for each before execution.
The Trivy archive hash is
`8b4376d5d6befe5c24d503f10ff136d9e0c49f9127a4279fd110b727929a5aa9` before execution. Trivy's
database is fetched from the official `ghcr.io/aquasecurity/trivy-db` source into `.local/cache`.
No scanner credential is stored in the repository or passed on a command line.

The workflow uses read-only repository permission. OpenGrep is an LGPL-2.1 Semgrep-compatible fork;
CI places its standalone official release under `.local/tools`, uses only the committed ruleset whose
normalized-content SHA-256 is pinned in policy, disables the remote version check, and requires a
runtime-generated code-injection canary. It neither uploads source nor downloads rules at runtime.
The workflow does not upload raw
scanner output and does not persist an SBOM before container images exist. Dependency/image
metadata is Medium; any future scanner credential remains Critical and belongs only in the approved
credential store or secret manager.

## Local verification

Use the workspace `.venv` and workspace-local caches only. Installing or downloading tools requires
the normal explicit source/version/destination approval.

```powershell
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check `
  --cache-dir .local\cache\pip -r requirements-security-tools.txt
.\.venv\Scripts\python.exe scripts\check_security_scanning_policy.py
.\.venv\Scripts\python.exe scripts\test_security_scanners_canary.py pip-audit
.\.venv\Scripts\python.exe scripts\test_security_scanners_canary.py bandit
.\.venv\Scripts\python.exe scripts\test_security_scanners_canary.py trivy `
  --trivy .local\tools\trivy\0.70.0\trivy.exe
.\.venv\Scripts\pip-audit.exe --strict --cache-dir .local\cache\pip-audit `
  --requirement requirements-security-audit.txt
.\.venv\Scripts\bandit.exe -q -r services packages workers scripts -lll
.\.local\tools\trivy\0.70.0\trivy.exe --cache-dir .local\cache\trivy fs `
  --scanners vuln,misconfig --severity HIGH,CRITICAL --exit-code 1 --no-progress `
  --skip-check-update --offline-scan --disable-telemetry --skip-version-check .
```

The local canary command generates synthetic vulnerable files under `.local/tmp`, parses structured
finding counts without printing raw output, and verifies pip-audit, Bandit, and Trivy reject them.
The OpenGrep canary uses the same helper and committed Semgrep-compatible rules before scanning
implementation source. Neither path reads `.env`, media, evidence, or runtime data. The exact
OpenGrep gate is CI-only: the Windows launcher attempts to use profile-owned paths even when the
download is workspace-local, so it is prohibited by this project's containment policy. Do not
install or run OpenGrep globally as a workaround.

## Dependency inventory and updates

`scripts/check_security_scanning_policy.py` derives every external exact direct pin from project
`pyproject.toml` files, `requirements-quality.txt`, and `requirements-security-tools.txt`. CI fails if
`requirements-security-audit.txt` drifts or any direct declaration is not an exact pin. Project-owned
`camera-ai-*` packages are excluded from the external audit input but remain covered by SAST and the
repository quality gates.

Dependabot groups Python, npm, and GitHub Actions security updates and groups routine minor/patch
updates to keep review volume bounded. Dependabot PRs still require the same checks and review; they
are never auto-merged by this configuration.

## Finding response and exceptions

- Critical: blocks merge. No policy exception is allowed.
- High: blocks release, has a seven-day remediation SLA, and currently also fails pull requests to
  prevent introducing new exposure.
- Medium: has a 30-day remediation SLA and must remain visible for triage.

Do not paste raw scanner logs into public issues. Record only package/rule identifier, severity,
affected implementation path, safe remediation summary, owner, and workflow URL. If a non-Critical
temporary exception is unavoidable, add a reviewed entry to
`security-scanning-exceptions-v1.json`; all required fields must be non-empty and `expires_on` must be
an ISO date that has not passed. Expired exceptions fail CI. The registry does not suppress scanner
execution by itself, so a scanner failure still fails closed until an explicitly reviewed scoped
suppression mechanism is implemented.

For a suspected scanner compromise or malicious package: stop the affected workflow/release lane,
preserve only sanitized metadata, rotate any potentially exposed scanner credential through the
approved store, verify upstream provenance, and require security review before repinning. Do not
delete caches or runtime state without resolving the exact workspace-local target and obtaining the
required approval.

## Activation gates

There is no tracked Dockerfile and no approved staging API today. Consequently:

- the first Dockerfile change must activate Trivy image scanning by immutable digest, produce a
  CycloneDX or SPDX SBOM, record its digest, and restrict artifact access;
- the approved staging API change must add OWASP ZAP baseline scanning against a fixed non-user-
  controlled HTTPS target and make it required before production promotion.

`check_security_scanning_policy.py` immediately fails if a Dockerfile appears while the image/SBOM
gate remains blocked. DAST stays fail-closed until the staging target and environment approval exist;
this repository does not invent or probe a target.
