$ErrorActionPreference = "Stop"

$repo = "HIepNgoc2006/Camera-AI"

function Invoke-Gh {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
  & gh @Args
  if ($LASTEXITCODE -ne 0) {
    throw "gh command failed: gh $($Args -join ' ')"
  }
}

function Ensure-Issue {
  param(
    [string]$Title,
    [string]$Body,
    [string]$Labels,
    [string]$Milestone
  )

  if ($script:ExistingIssueTitles.Contains($Title)) {
    Write-Output "exists issue: $Title"
    return
  }

  Invoke-Gh issue create --repo $repo --title $Title --body $Body --label $Labels --milestone $Milestone
  $script:CreatedIssues += $Title
  $script:ExistingIssueTitles.Add($Title) | Out-Null
  Write-Output "created issue: $Title"
}

Write-Output "Checking repo access: $repo"
Invoke-Gh repo view $repo --json "name,owner,url,visibility"

$existingIssuesJson = gh issue list --repo $repo --state all --limit 500 --json title
$existingIssues = $existingIssuesJson | ConvertFrom-Json
$script:ExistingIssueTitles = [System.Collections.Generic.HashSet[string]]::new()
foreach ($issue in $existingIssues) {
  $script:ExistingIssueTitles.Add([string]$issue.title) | Out-Null
}

$script:CreatedIssues = @()

$issues = @(
  @{
    Title = "[BE] Define OpenAPI and error response standard"
    Milestone = "M3 - Backend Core"
    Labels = "type:docs,area:backend,priority:critical"
    Body = "Define API contract rules before Web/Mobile integration.`n`nAcceptance:`n- OpenAPI generation/spec strategy is defined.`n- Stable error response shape is defined.`n- Auth, permission and audit behavior are required per API.`n- No stack traces or internal secrets are returned."
  },
  @{
    Title = "[BE] Build Camera Registry Service"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:high"
    Body = "Plan/build Camera Registry Service for camera metadata, zones and ANSVIS mapping.`n`nAcceptance:`n- Camera metadata model is defined.`n- Zone and ANSVIS mapping are defined.`n- Real RTSP credentials are not stored in business tables.`n- Permission and audit behavior are defined."
  },
  @{
    Title = "[BE] Build Event Ingestion Service"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:feature,area:backend,priority:critical,risk:production"
    Body = "Plan/build Event Ingestion Service for validated AI events.`n`nAcceptance:`n- Event validation, normalization and idempotency are covered.`n- Queue/outbox behavior is defined.`n- Raw media/base64 is not logged.`n- Duplicate events do not create duplicate business records."
  },
  @{
    Title = "[BE] Build Attendance Service"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:critical,risk:biometric"
    Body = "Plan/build Attendance Service for student attendance and late handling.`n`nAcceptance:`n- Attendance records are scoped by role/object authorization.`n- Consent behavior is defined for biometric attendance.`n- Manual review/correction is audited.`n- Fake data only in tests."
  },
  @{
    Title = "[BE] Build Timekeeping Service"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:high"
    Body = "Plan/build Timekeeping Service for staff/teacher check-in/out.`n`nAcceptance:`n- Staff time records and corrections are defined.`n- Permission and audit behavior are defined.`n- Reports use correct timezone policy."
  },
  @{
    Title = "[BE] Build Violation Service"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:high,risk:customer-impact"
    Body = "Plan/build Violation Service for uniform, late, littering, smoking and kitchen protection events.`n`nAcceptance:`n- Violation types and review statuses are defined.`n- Human review/correction flow is covered.`n- Evidence access goes through Evidence Storage policy.`n- False positive appeal path is supported."
  },
  @{
    Title = "[BE] Build Notification Service"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:high,risk:data-leak"
    Body = "Plan/build Notification Service for in-app/push/email rules.`n`nAcceptance:`n- Recipient permission check is required.`n- Push content avoids sensitive details/media.`n- Delivery log and retry behavior are defined.`n- Device token protection is defined."
  },
  @{
    Title = "[BE] Build Report and Export Service"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:high,risk:data-leak"
    Body = "Plan/build Report and Export Service for dashboard and exports.`n`nAcceptance:`n- Report scopes follow role/object authorization.`n- Export actions are audited.`n- Heavy export uses async/rate limit strategy.`n- Export files have TTL if stored."
  },
  @{
    Title = "[BE] Build Evidence Storage Service"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,area:database,priority:critical,risk:data-leak"
    Body = "Plan/build Evidence Storage Service for image/video metadata and signed URLs.`n`nAcceptance:`n- PostgreSQL stores metadata only, not binary/base64 media.`n- Object storage is private.`n- Signed URL TTL and audit are required.`n- Retention policy is defined."
  },
  @{
    Title = "[BE] Build AI Model Registry Service"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:feature,area:backend,area:ai-model,priority:high"
    Body = "Plan/build AI Model Registry Service for model/dataset/artifact metadata.`n`nAcceptance:`n- Model version, metric, dataset hash and approval status are tracked.`n- Artifact checksum is required.`n- No real dataset/model secret is committed."
  },
  @{
    Title = "[BE] Build Retention and Data Lifecycle Job"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:database,priority:critical,risk:biometric"
    Body = "Plan/build retention/delete/anonymize jobs.`n`nAcceptance:`n- Dry-run mode is required.`n- Sensitive delete/anonymize actions are audited.`n- Consent withdrawal path is handled.`n- Backup/restore impact is documented."
  },
  @{
    Title = "[WEB] Build login MFA and session timeout UI"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high,risk:permission"
    Body = "Plan/build Web login, MFA and session timeout UI.`n`nAcceptance:`n- Admin/BGH MFA flow is supported.`n- Session timeout/logout behavior is clear.`n- Errors do not expose internal details."
  },
  @{
    Title = "[WEB] Build BGH dashboard"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high"
    Body = "Plan/build BGH dashboard.`n`nAcceptance:`n- Attendance, violation, camera and alert overview are covered.`n- Data is filtered by authorized scope.`n- Empty/error/loading states are defined."
  },
  @{
    Title = "[WEB] Build attendance view"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high,risk:permission"
    Body = "Plan/build attendance view by class/day/role.`n`nAcceptance:`n- Parent/teacher/BGH/admin scopes are respected.`n- Manual correction path is audited where supported.`n- Unauthorized data is not rendered."
  },
  @{
    Title = "[WEB] Build violation review screen"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high,risk:customer-impact"
    Body = "Plan/build violation review screen.`n`nAcceptance:`n- Review/approve/reject/correction statuses are supported.`n- Evidence requires permission and signed URL policy.`n- AI false alert handling is visible."
  },
  @{
    Title = "[WEB] Build report and export screen"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high,risk:data-leak"
    Body = "Plan/build report and export UI.`n`nAcceptance:`n- Export scope is permission-limited.`n- Export action requires audit.`n- Heavy export and loading state are handled."
  },
  @{
    Title = "[WEB] Build user role admin screen"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high,risk:permission"
    Body = "Plan/build user, role and permission admin screen.`n`nAcceptance:`n- Only authorized admins can manage roles.`n- Permission changes are audited.`n- Dangerous changes have confirmation."
  },
  @{
    Title = "[WEB] Build consent privacy screen"
    Milestone = "M5 - Web Portal"
    Labels = "type:security,area:web,priority:critical,risk:biometric"
    Body = "Plan/build consent and privacy management screen.`n`nAcceptance:`n- Consent status is visible to authorized roles.`n- Consent withdrawal flow is supported according to policy.`n- Consent changes are audited."
  },
  @{
    Title = "[WEB] Build camera ANSVIS status screen"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:medium"
    Body = "Plan/build camera and ANSVIS status screen.`n`nAcceptance:`n- Camera/task/event health is visible.`n- No credentials are displayed.`n- Operators can identify integration issues."
  },
  @{
    Title = "[WEB] Harden Web Portal security"
    Milestone = "M5 - Web Portal"
    Labels = "type:security,area:web,priority:critical,risk:permission"
    Body = "Plan Web Portal security hardening.`n`nAcceptance:`n- Route guards are applied.`n- XSS/CSRF/IDOR checklist is covered.`n- Unauthorized UI actions are hidden but backend remains final enforcement.`n- Sensitive evidence is permission-gated."
  },
  @{
    Title = "[MOB] Build mobile auth refresh and logout flow"
    Milestone = "M6 - Mobile App"
    Labels = "type:feature,area:mobile,priority:high,risk:permission"
    Body = "Plan/build mobile login, refresh and logout flow.`n`nAcceptance:`n- Token refresh/revoke behavior is defined.`n- Logout clears sensitive local state.`n- Errors do not expose internal details."
  },
  @{
    Title = "[MOB] Implement secure token storage"
    Milestone = "M6 - Mobile App"
    Labels = "type:security,area:mobile,priority:critical,risk:data-leak"
    Body = "Plan/build secure mobile token storage.`n`nAcceptance:`n- Keychain/Keystore approach is selected.`n- Tokens are not stored in plaintext AsyncStorage/local files.`n- Lost-device revoke flow is compatible."
  },
  @{
    Title = "[MOB] Build parent home screen"
    Milestone = "M6 - Mobile App"
    Labels = "type:feature,area:mobile,priority:high"
    Body = "Plan/build parent home screen.`n`nAcceptance:`n- Parent sees only authorized child summary.`n- No sensitive evidence is shown by default.`n- Empty/error/loading states are defined."
  },
  @{
    Title = "[MOB] Build child attendance screen"
    Milestone = "M6 - Mobile App"
    Labels = "type:feature,area:mobile,priority:high,risk:permission"
    Body = "Plan/build child attendance screen.`n`nAcceptance:`n- Parent can only view own child attendance.`n- Teacher/BGH role handling is explicit if used.`n- Unauthorized access is blocked."
  },
  @{
    Title = "[MOB] Build notification list and detail"
    Milestone = "M6 - Mobile App"
    Labels = "type:feature,area:mobile,priority:high,risk:data-leak"
    Body = "Plan/build mobile notification list/detail.`n`nAcceptance:`n- Notification content follows privacy policy.`n- Recipient permission is respected.`n- Sensitive media is not embedded in push."
  },
  @{
    Title = "[MOB] Build event detail permission guard"
    Milestone = "M6 - Mobile App"
    Labels = "type:security,area:mobile,priority:critical,risk:permission"
    Body = "Plan/build permission guard for event/evidence detail.`n`nAcceptance:`n- Evidence is only shown to authorized users.`n- Signed URL policy is respected.`n- Unauthorized user gets safe error/empty state."
  },
  @{
    Title = "[MOB] Build consent flow"
    Milestone = "M6 - Mobile App"
    Labels = "type:security,area:mobile,priority:critical,risk:biometric"
    Body = "Plan/build mobile consent flow.`n`nAcceptance:`n- Parent can view consent status and policy.`n- Consent grant/withdraw path is clear.`n- Changes are audited by backend."
  },
  @{
    Title = "[MOB] Build push token lifecycle"
    Milestone = "M6 - Mobile App"
    Labels = "type:feature,area:mobile,priority:high"
    Body = "Plan/build push device token registration and revoke lifecycle.`n`nAcceptance:`n- Device token register/update/revoke is defined.`n- Logout/lost-device revoke behavior is covered.`n- Device token is protected."
  },
  @{
    Title = "[MOB] Harden production mobile build"
    Milestone = "M6 - Mobile App"
    Labels = "type:security,area:mobile,priority:critical,risk:data-leak"
    Body = "Plan production mobile hardening.`n`nAcceptance:`n- Debug logs are disabled in production.`n- Sensitive screens avoid leaking data where possible.`n- Production build config is reviewed."
  },
  @{
    Title = "[QA] Define UAT acceptance matrix"
    Milestone = "M9 - UAT & Go-live"
    Labels = "type:qa,area:qa,priority:critical,risk:customer-impact"
    Body = "Define UAT acceptance matrix by module before customer acceptance.`n`nAcceptance:`n- Auth, attendance, timekeeping, violation, notification, report, consent, security and operations acceptance criteria are listed.`n- Blocker/Critical/High handling rules are clear.`n- UAT evidence format is defined."
  },
  @{
    Title = "[QA] Define production readiness gate checklist"
    Milestone = "M8 - Security Hardening"
    Labels = "type:qa,area:qa,priority:critical,risk:production"
    Body = "Define production readiness gate checklist before implementation/go-live.`n`nAcceptance:`n- Security, backup/restore, rollback, monitoring, consent, RBAC, scan and incident response gates are listed.`n- Missing gate blocks go-live.`n- Evidence required per gate is defined."
  }
)

foreach ($issue in $issues) {
  Ensure-Issue -Title $issue.Title -Body $issue.Body -Labels $issue.Labels -Milestone $issue.Milestone
}

Write-Output "Summary"
Write-Output "Created issues: $($script:CreatedIssues.Count)"
foreach ($title in $script:CreatedIssues) {
  Write-Output "- $title"
}\n