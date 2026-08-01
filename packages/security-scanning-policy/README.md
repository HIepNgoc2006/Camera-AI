# Security scanning policy contract

This package is the machine-readable authority for Issue #112. It contains no credentials,
customer data, vulnerability reports, images, or production identifiers.

- `security-scanning-policy-v1.json` pins merge scanners, thresholds, canary behavior, approved
  network sources, remediation SLAs, and fail-closed activation gates.
- `security-scanning-exceptions-v1.json` is the reviewed exception registry. An exception must have
  exactly the required owner, approval, justification, compensating control, finding reference, and
  expiry fields. An expired or malformed entry fails CI. Critical merge exceptions are prohibited.

The policy intentionally leaves image scanning/SBOM and DAST blocked. The first tracked Dockerfile
must activate immutable-digest image scanning and SBOM evidence in the same change. DAST may be
activated only after an approved fixed staging API target and pre-production environment gate exist.
Neither blocked gate is permission to skip it before its trigger occurs.

Run `python scripts/check_security_scanning_policy.py` after any dependency, scanner, workflow,
Dockerfile, exception, or activation-status change. Operational commands and incident handling are
documented in `docs/security/supply-chain-scanning.md`.
