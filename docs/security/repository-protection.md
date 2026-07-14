# Repository protection baseline

The `main` branch is protected for the single-developer delivery model. Changes require a pull
request and an up-to-date branch. The required GitHub checks are `python-quality` and `secret-scan`.
Protection applies to administrators; force-push and branch deletion are disabled, and review
conversations must be resolved before merge. The approval count is zero because the project has one
primary developer, but the pull-request and automated-check gates remain mandatory.

Repository administrators can audit the configuration without printing credentials:

```powershell
rtk gh api repos/HIepNgoc2006/Camera-AI/branches/main/protection
```

Changing required checks, bypass behavior, force-push, deletion, or administrator enforcement is a
security-sensitive repository change. Record the reason, expected impact, rollback, and resulting
protection summary. Never weaken protection merely to merge a failing change.
