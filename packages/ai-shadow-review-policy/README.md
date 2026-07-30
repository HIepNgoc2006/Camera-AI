# AI shadow and human-review policy

`ai-shadow-review-policy-v1.json` is the versioned, machine-readable baseline for safe AI
evaluation. It covers Facial Recognition, Littering Detection, suspected Smoking Detection,
Student Uniform Detection and Kitchen PPE Detection.

The published v1 contract is deliberately `baseline_only` with runtime activation `disabled`.
Shipping this package does not start an ANSVIS task, approve a model, change a camera, enable a
pipeline or authorize production use. Activation requires every named per-pipeline gate plus a
separate approved change record.

## Decision boundary

The policy produces controlled evaluation/review outcomes, never an automatic disciplinary
conclusion:

| Input condition | Policy outcome |
|---|---|
| Policy/task disabled | Block |
| Missing required biometric consent | Block |
| Unknown or partial visibility | Explicit non-decision |
| Low/unknown confidence | Human review required |
| Littering without multi-frame temporal evidence | Human review required |
| Any custom violation pipeline without completed review | Human review required |
| Valid shadow observation | Record sanitized evaluation metadata only |
| Human reviewer confirms/rejects | Controlled review result for the owning business service |

The owning Attendance, Timekeeping or Violation service remains responsible for authorization,
consent, business rules, immutable history, correction/appeal and audit. A policy result is not a
business record.

Every lifecycle edge names one responsible authority. Production additionally requires a
per-pipeline metric profile and sanitized references for evaluation, provenance/consent review,
capacity, approval, exact model/config/task versions and rollback evidence. Missing or unknown gates
deny activation.

## Pipeline guardrails

- Facial Recognition emits a match candidate. Consent and a separate attendance/timekeeping rule
  are required before a business record can exist.
- Littering requires temporal behavior evidence; a single frame containing garbage is insufficient.
- Smoking is always worded `suspected_smoking` before review.
- Student Uniform and Kitchen PPE return `unknown` or `partial_visibility` rather than forcing a
  pass/fail result when required regions are obscured.
- Rollback/disable targets one exact pipeline/model/config/task version and cannot enable another
  pipeline or delete audit evidence.

## Local verification

```powershell
rtk .\.venv\Scripts\python.exe scripts/quality.py ai-shadow-review-policy
rtk .\.venv\Scripts\python.exe -m pytest -q scripts/tests/test_ai_shadow_review_policy.py
```

Fixtures use synthetic identifiers only. Do not add images, video, face data, raw ANSVIS payloads,
signed URLs, credentials, real camera topology or personal data to this package.
