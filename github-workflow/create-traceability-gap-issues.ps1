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
    Title = "[AI] Define 34-camera task mapping matrix"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:ai,area:ansvis,priority:critical,risk:production"
    Body = "Create the mapping matrix for all 34 cameras and related AI tasks.`n`nAcceptance:`n- 16 attendance/happiness cameras, 8 littering cameras, 8 smoking cameras and 2 kitchen/PPE cameras are represented.`n- Each row has camera ID/name, location, ANSVIS task, event type, ROI/line/zone, threshold, schedule and owner.`n- No physical installation task is added; this is software/integration mapping only."
  },
  @{
    Title = "[AI] Define happiness index scope and privacy guardrails"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:ai,area:ai-model,priority:critical,risk:customer-impact,risk:biometric"
    Body = "Clarify the scope and privacy guardrails for the happiness/wellbeing index before implementation.`n`nAcceptance:`n- Purpose, user-facing wording and allowed use are defined.`n- It is not used for disciplinary decisions without human review and approved policy.`n- Consent/data minimization/privacy handling are defined.`n- If scope is rejected/deferred, the decision is documented."
  },
  @{
    Title = "[AI] Define per-pipeline AI acceptance metrics"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:ai,area:ai-model,priority:high,risk:customer-impact"
    Body = "Define acceptance metrics for each AI model/pipeline.`n`nAcceptance:`n- Facial Recognition metrics cover false match, missed match, threshold and consent.`n- Littering, Smoking, Student Uniform and Kitchen PPE metrics are defined separately.`n- Precision/recall or false-positive/false-negative review criteria are defined.`n- Human review thresholds and appeal/correction path are referenced.`n- Metrics use approved camera/ANSVIS data only when real data is required."
  },
  @{
    Title = "[WEB] Build parent portal view"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high,risk:permission"
    Body = "Add Web Portal coverage for parent role because customer docs mention parent web access.`n`nAcceptance:`n- Parent can view only their own child data.`n- Attendance/notification/event visibility follows permission and evidence policy.`n- Unauthorized child/class data is not rendered.`n- Backend authorization remains final enforcement."
  },
  @{
    Title = "[WEB] Build teacher class view"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high,risk:permission"
    Body = "Add Web Portal coverage for teacher class view.`n`nAcceptance:`n- Teacher sees only assigned classes/students.`n- Attendance and relevant events are scoped correctly.`n- Any correction/review action is audited if supported."
  },
  @{
    Title = "[QA] Define 34-camera performance benchmark plan"
    Milestone = "M7 - Integration & QA"
    Labels = "type:qa,area:qa,priority:high,risk:production"
    Body = "Define performance benchmark plan for 34-camera operating assumptions.`n`nAcceptance:`n- Event ingestion throughput, queue backlog, DB insert/read, notification and report impact are covered.`n- ANSVIS/GPU/license capacity assumptions are linked.`n- Test uses staging/pilot and sanitized payloads, not destructive production traffic."
  },
  @{
    Title = "[OPS] Define deployment architecture and capacity baseline"
    Milestone = "M8 - Security Hardening"
    Labels = "type:ops,area:devops,priority:high,risk:production"
    Body = "Define deployment architecture and capacity baseline before production decisions.`n`nAcceptance:`n- Server layout, network boundaries, PostgreSQL, Redis, RabbitMQ, object storage and monitoring are described.`n- ANSVIS/AIBOX machine/GPU/license assumptions are listed.`n- Backup, restore, TLS, firewall and rollback dependencies are referenced."
  },
  @{
    Title = "[DOCS] Maintain requirements-to-issues traceability matrix"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:docs,area:docs,priority:high"
    Body = "Maintain a traceability matrix between customer requirements, planning docs and GitHub Issues.`n`nAcceptance:`n- Core requirements map to docs and issue numbers.`n- Gaps are listed with actions.`n- The matrix is updated when new scope is added or deferred."
  }
)

foreach ($issue in $issues) {
  Ensure-Issue -Title $issue.Title -Body $issue.Body -Labels $issue.Labels -Milestone $issue.Milestone
}

Write-Output "Summary"
Write-Output "Created issues: $($script:CreatedIssues.Count)"
foreach ($title in $script:CreatedIssues) {
  Write-Output "- $title"
}
