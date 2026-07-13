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

$existingIssuesJson = gh issue list --repo $repo --state all --limit 300 --json title
$existingIssues = $existingIssuesJson | ConvertFrom-Json
$script:ExistingIssueTitles = [System.Collections.Generic.HashSet[string]]::new()
foreach ($issue in $existingIssues) {
  $script:ExistingIssueTitles.Add([string]$issue.title) | Out-Null
}

$script:CreatedIssues = @()

$issues = @(
  @{
    Title = "[OPS] Add NTP and timezone synchronization policy"
    Milestone = "M7 - Integration & QA"
    Labels = "type:ops,area:devops,priority:high,risk:production"
    Body = "Define and verify time synchronization for camera, ANSVIS, backend, database, logs, and reports.`n`nAcceptance:`n- NTP/timezone policy documented.`n- Timestamp handling is included in E2E tests.`n- Attendance/late/timekeeping logic uses consistent timezone."
  },
  @{
    Title = "[AI] Verify ANSVIS license, task limit and GPU capacity"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:ai,area:ansvis,priority:critical,risk:production"
    Body = "Verify ANSVIS version, license limits, max running AI tasks, GPU/CPU capacity and impact for 34 cameras.`n`nAcceptance:`n- License/task limit documented.`n- GPU/CPU capacity assumptions documented.`n- Pilot benchmark plan exists."
  },
  @{
    Title = "[SEC] Define signed URL TTL and evidence access audit"
    Milestone = "M8 - Security Hardening"
    Labels = "type:security,area:security,priority:critical,risk:data-leak"
    Body = "Define signed URL TTL, access audit, and evidence export policy for event images/videos.`n`nAcceptance:`n- Signed URL TTL defined.`n- Evidence view/export audit required.`n- No public bucket or permanent public URL."
  },
  @{
    Title = "[SEC] Define notification privacy policy"
    Milestone = "M7 - Integration & QA"
    Labels = "type:security,area:security,priority:critical,risk:data-leak"
    Body = "Define safe notification content rules for push/in-app/email.`n`nAcceptance:`n- Push notification does not include sensitive image/face/violation details.`n- Recipient permission check is required.`n- Delivery audit is required for sensitive notification."
  },
  @{
    Title = "[SEC] Define consent withdrawal and data deletion workflow"
    Milestone = "M8 - Security Hardening"
    Labels = "type:security,area:security,priority:critical,risk:biometric"
    Body = "Define workflow when parent/student consent is withdrawn.`n`nAcceptance:`n- Processing stops when consent is withdrawn.`n- Related biometric data deletion/anonymization path is documented.`n- Audit trail is required."
  },
  @{
    Title = "[OPS] Add backup restore drill task"
    Milestone = "M8 - Security Hardening"
    Labels = "type:ops,area:devops,priority:critical,risk:production"
    Body = "Run and document backup restore drill for database, object storage, model artifacts, and ANSVIS config limitations.`n`nAcceptance:`n- Restore drill checklist exists.`n- Restore evidence required before go-live.`n- ANSVIS face DB/model/license backup limitations are documented."
  },
  @{
    Title = "[OPS] Add queue backpressure and DLQ alert policy"
    Milestone = "M7 - Integration & QA"
    Labels = "type:ops,area:devops,priority:high,risk:production"
    Body = "Define queue limits, retry limits, DLQ policy, and backlog alerts for event ingestion/notification/report workers.`n`nAcceptance:`n- Retry/backoff policy documented.`n- DLQ alert threshold defined.`n- Queue backlog dashboard requirement exists."
  },
  @{
    Title = "[MOB] Add lost-device and session revoke flow"
    Milestone = "M6 - Mobile App"
    Labels = "type:feature,area:mobile,priority:high,risk:permission"
    Body = "Define and implement mobile lost-device response: revoke token, logout all devices, refresh token rotation.`n`nAcceptance:`n- Secure storage is used.`n- User/admin can revoke sessions.`n- Token revoke test exists."
  },
  @{
    Title = "[AI] Add model drift monitoring plan"
    Milestone = "M9 - UAT & Go-live"
    Labels = "type:ai,area:ai-model,priority:high,risk:customer-impact"
    Body = "Define post-go-live model drift monitoring for false alerts, missed detections, confidence distribution, and retraining triggers.`n`nAcceptance:`n- Drift metrics defined.`n- Review cadence defined.`n- Retrain/recalibration trigger documented."
  },
  @{
    Title = "[QA] Add report and export load test"
    Milestone = "M7 - Integration & QA"
    Labels = "type:qa,area:qa,priority:high,risk:production"
    Body = "Test report/export performance and abuse resistance.`n`nAcceptance:`n- Heavy report query cases defined.`n- Async export/rate limit requirement checked.`n- DB impact measured or bounded."
  },
  @{
    Title = "[QA] Add environment misconfiguration checklist"
    Milestone = "M8 - Security Hardening"
    Labels = "type:qa,area:qa,priority:high,risk:production"
    Body = "Create checklist to prevent staging/production config and secret mix-ups.`n`nAcceptance:`n- Environment variables validated.`n- Production debug flags checked.`n- Secret source per environment documented."
  },
  @{
    Title = "[SEC] Add data fixture and seed data safety check"
    Milestone = "M2 - Codebase Foundation"
    Labels = "type:security,area:security,priority:critical,risk:data-leak"
    Body = "Ensure test fixtures and seed data use fake/sanitized data only.`n`nAcceptance:`n- No real student/parent/face/camera data in fixtures.`n- Fixture review checklist exists.`n- Seed data naming convention is documented."
  },
  @{
    Title = "[OPS] Add staging-production parity checklist"
    Milestone = "M8 - Security Hardening"
    Labels = "type:ops,area:devops,priority:high,risk:production"
    Body = "Create staging-production parity checklist for services, environment variables, reverse proxy, storage, queue, monitoring and security controls.`n`nAcceptance:`n- Parity checklist exists.`n- Known differences are documented.`n- Go-live requires parity review."
  },
  @{
    Title = "[OPS] Add ANSVIS backup limitation checklist"
    Milestone = "M8 - Security Hardening"
    Labels = "type:ops,area:ansvis,priority:high,risk:production"
    Body = "Document ANSVIS backup limitations and required separate backup for uploaded models, face DB, license DB and dataset artifacts where applicable.`n`nAcceptance:`n- ANSVIS restore point limitations documented.`n- Separate backup responsibilities documented.`n- Restore test plan includes ANSVIS components."
  },
  @{
    Title = "[QA] Add AI appeal and manual correction workflow test"
    Milestone = "M7 - Integration & QA"
    Labels = "type:qa,area:qa,priority:high,risk:customer-impact"
    Body = "Test workflow for AI false positive/false negative appeal and manual correction.`n`nAcceptance:`n- User can report incorrect AI event if allowed.`n- Admin/teacher can review and correct.`n- Correction is audited."
  },
  @{
    Title = "[SEC] Define DDoS threat model and protection strategy"
    Milestone = "M8 - Security Hardening"
    Labels = "type:security,area:security,priority:high,risk:production"
    Body = "Define DDoS and abuse traffic threat model for Web, Mobile API, ANSVIS webhook, export/report and object storage access.`n`nAcceptance:`n- Public attack surfaces listed.`n- WAF/CDN/rate limit strategy defined.`n- Monitoring signals defined."
  },
  @{
    Title = "[SEC] Harden ANSVIS webhook against flood, replay and large payload"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:security,area:ansvis,priority:critical,risk:production"
    Body = "Harden ANSVIS webhook against request flood, replay, malformed payload and oversized body.`n`nAcceptance:`n- HMAC/token/source validation required.`n- Body size limit required.`n- Idempotency/replay protection tested.`n- Invalid payload safely rejected."
  },
  @{
    Title = "[QA] Add DDoS and abuse traffic test plan"
    Milestone = "M7 - Integration & QA"
    Labels = "type:qa,area:qa,priority:high,risk:production"
    Body = "Create safe abuse/load test plan for API rate limits, login throttling, report/export limits and webhook flood handling using sanitized payloads.`n`nAcceptance:`n- No destructive production test.`n- Staging test cases defined.`n- Expected throttle/reject behavior documented."
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