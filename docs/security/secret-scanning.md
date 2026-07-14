# Secret and sensitive-file scanning

The repository uses gitleaks 8.30.1 plus a tracked-path policy check. Scanner output is always redacted; never paste a real finding value into a terminal transcript, issue, PR, log, or chat.

## Local verification

Run from the repository root:

```powershell
rtk python scripts/check_repository_safety.py
rtk python -m unittest discover -s scripts/tests -p "test_*.py"
rtk gitleaks git --config .gitleaks.toml --redact --no-banner --no-color
rtk python scripts/test_gitleaks_canary.py
```

Before commit, also scan only staged content:

```powershell
rtk gitleaks git --staged --config .gitleaks.toml --redact --no-banner --no-color
```

The canary script constructs a fake ANSVIS credential only inside an operating-system temporary directory. It captures and discards scanner output, reports only pass/fail status, and never commits the complete canary value.

## Covered controls

- Default gitleaks rules for common tokens, credentials, and private keys.
- Project rules for credentialed RTSP URLs and ANSVIS credential assignments.
- Unsafe `.env` variants, service-account JSON, keys, dumps, local planning/reference paths, datasets, evidence, backups, logs, media, and model artifacts.
- Generic tracked files larger than 10 MiB.

The path policy reports only a filename and stable category. It never reads or prints file contents.

## CI behavior

The workflow runs on pull requests, pushes to `main`, and manual dispatch. It uses read-only repository permissions, a commit-pinned checkout action, and the exact gitleaks image version and digest. CI must pass both the clean scan and the runtime-generated negative canary test.

## Finding and remediation

If a finding is uncommitted:

1. Stop staging or committing.
2. Record only the path, rule/category, and remediation status.
3. Remove the value from the implementation and load it through approved local environment injection or a secret manager.
4. Re-run path, staged, and history scans.

If a secret was committed locally but not pushed, stop and remove it from local history using the least destructive reviewed method before any push.

If a secret, real personal/biometric data, evidence, camera credential, or production configuration was pushed, treat it as a security incident. Revoke/rotate or block access immediately through the approved owner, preserve audit evidence without copying the value, stop merge/release, and escalate for history purge and impact/notification assessment. Deleting a branch alone is not sufficient.
