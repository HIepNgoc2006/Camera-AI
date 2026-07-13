# GitHub issue templates

Mọi issue triển khai phải có mục sau. Nếu không phụ thuộc issue khác, ghi rõ `Blocked by: None` thay vì bỏ trống.

```markdown
## Dependencies
- Blocked by: #issue hoặc None
- Blocks: #issue hoặc None
- Execution order: vị trí trong chuỗi tuần tự của milestone
```

Các template này có thể copy vào `.github/ISSUE_TEMPLATE/` khi repo bắt đầu code chính thức. Hiện tại lưu ở đây để tránh tạo quá nhiều config khi chưa cần.

## Feature issue

```markdown
## Goal

## Scope

## User / Role affected

## Data classification
- [ ] No sensitive data
- [ ] Student/parent data
- [ ] Attendance/timekeeping
- [ ] Event image/video
- [ ] Biometric/face data
- [ ] Secret/config

## Security / privacy impact

## Acceptance criteria
- [ ] Expected behavior/output is clearly described
- [ ] Security/privacy impact is handled if relevant

## Definition of Done
- [ ] Code/docs implemented
- [ ] Tests added/updated
- [ ] Permission checked
- [ ] Audit added if sensitive
- [ ] Docs/runbook updated if needed

## Evidence required
```

## Bug issue

```markdown
## Environment

## Steps to reproduce
1.
2.
3.

## Expected result

## Actual result

## Severity
- [ ] Critical
- [ ] High
- [ ] Medium
- [ ] Low

## Sensitive data involved?
- [ ] No
- [ ] Yes, describe without exposing real data:

## Logs / request ID / event ID

## Root cause

## Fix verification
```

## Security issue

```markdown
## Summary

## Affected data
- [ ] Secret/config
- [ ] Student/parent data
- [ ] Face/biometric data
- [ ] Event image/video
- [ ] Permission/audit
- [ ] Production infrastructure

## Impact

## Exploitability

## Temporary mitigation

## Permanent fix

## Secret rotation needed?
- [ ] No
- [ ] Yes

## Notification needed?
- [ ] No
- [ ] Need review
- [ ] Yes

## Verification
```

## AI / ANSVIS issue

```markdown
## Goal

## ANSVIS / AI component
- [ ] Camera mapping
- [ ] HTTP Trigger
- [ ] Event payload
- [ ] Event ingestion
- [ ] Face recognition
- [ ] Model training
- [ ] Dataset
- [ ] Shadow mode

## Data classification

## Expected payload / behavior

## Security controls
- [ ] Token/HMAC/source validation
- [ ] Payload schema validation
- [ ] No raw media logging
- [ ] Idempotency
- [ ] Consent check if biometric

## Acceptance criteria

## Test evidence
```

## Docs issue

```markdown
## Document affected

## Change needed

## Audience
- [ ] Boss / management
- [ ] Customer / school
- [ ] Developer / agent
- [ ] Operations

## Acceptance criteria
- [ ] Clear and concise
- [ ] No broken links
- [ ] No unfinished placeholders
- [ ] Security/privacy impact covered if relevant
```

## Ops issue

```markdown
## Goal

## Component
- [ ] Docker
- [ ] CI/CD
- [ ] Monitoring
- [ ] Backup/restore
- [ ] Secret management
- [ ] Release/rollback

## Risk level

## Steps

## Rollback plan

## Verification evidence
```
