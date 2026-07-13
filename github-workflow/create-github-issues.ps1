$ErrorActionPreference = "Stop"

$repo = "HIepNgoc2006/Camera-AI"

function Invoke-Gh {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
  & gh @Args
  if ($LASTEXITCODE -ne 0) {
    throw "gh command failed: gh $($Args -join ' ')"
  }
}

function Ensure-Label {
  param(
    [string]$Name,
    [string]$Color,
    [string]$Description
  )

  & gh label create $Name --repo $repo --color $Color --description $Description 2>$null
  if ($LASTEXITCODE -ne 0) {
    & gh label edit $Name --repo $repo --color $Color --description $Description 2>$null
    if ($LASTEXITCODE -ne 0) {
      throw "Cannot create or edit label: $Name"
    }
    Write-Output "updated label: $Name"
  } else {
    Write-Output "created label: $Name"
  }
}

function Ensure-Milestone {
  param([string]$Title)

  $milestonesJson = gh api "repos/$repo/milestones?state=all&per_page=100"
  $milestones = $milestonesJson | ConvertFrom-Json
  $exists = $false
  foreach ($m in $milestones) {
    if ($m.title -eq $Title) {
      $exists = $true
      break
    }
  }

  if (-not $exists) {
    Invoke-Gh api "repos/$repo/milestones" -f title="$Title"
    Write-Output "created milestone: $Title"
  } else {
    Write-Output "exists milestone: $Title"
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

$labels = @(
  @{ Name = "type:feature"; Color = "1D76DB"; Description = "Feature work" },
  @{ Name = "type:bug"; Color = "D73A4A"; Description = "Bug" },
  @{ Name = "type:security"; Color = "B60205"; Description = "Security or privacy issue" },
  @{ Name = "type:docs"; Color = "0075CA"; Description = "Documentation" },
  @{ Name = "type:ops"; Color = "5319E7"; Description = "Operations, DevOps, deployment" },
  @{ Name = "type:ai"; Color = "FBCA04"; Description = "AI, ANSVIS, model, event work" },
  @{ Name = "type:qa"; Color = "0E8A16"; Description = "Testing, UAT, acceptance" },

  @{ Name = "priority:critical"; Color = "B60205"; Description = "Critical priority" },
  @{ Name = "priority:high"; Color = "D93F0B"; Description = "High priority" },
  @{ Name = "priority:medium"; Color = "FBCA04"; Description = "Medium priority" },
  @{ Name = "priority:low"; Color = "C5DEF5"; Description = "Low priority" },

  @{ Name = "area:backend"; Color = "1D76DB"; Description = "Backend/API/service" },
  @{ Name = "area:web"; Color = "0E8A16"; Description = "Web Portal" },
  @{ Name = "area:mobile"; Color = "5319E7"; Description = "Mobile App" },
  @{ Name = "area:database"; Color = "006B75"; Description = "Database/schema/migration" },
  @{ Name = "area:ansvis"; Color = "7057FF"; Description = "ANSVIS/AIBOX integration" },
  @{ Name = "area:ai-model"; Color = "FBCA04"; Description = "AI model, dataset, training" },
  @{ Name = "area:security"; Color = "B60205"; Description = "Auth, RBAC, secret, audit, privacy" },
  @{ Name = "area:devops"; Color = "5319E7"; Description = "Docker, CI/CD, deploy" },
  @{ Name = "area:docs"; Color = "0075CA"; Description = "Documentation" },
  @{ Name = "area:qa"; Color = "0E8A16"; Description = "Testing and UAT" },

  @{ Name = "status:blocked"; Color = "D93F0B"; Description = "Blocked" },
  @{ Name = "status:needs-decision"; Color = "FBCA04"; Description = "Needs decision" },
  @{ Name = "status:needs-info"; Color = "C5DEF5"; Description = "Needs more information" },
  @{ Name = "status:ready"; Color = "0E8A16"; Description = "Ready to work" },

  @{ Name = "risk:data-leak"; Color = "B60205"; Description = "Data leakage risk" },
  @{ Name = "risk:biometric"; Color = "B60205"; Description = "Biometric/face data risk" },
  @{ Name = "risk:permission"; Color = "D93F0B"; Description = "Permission/access-control risk" },
  @{ Name = "risk:production"; Color = "D93F0B"; Description = "Production/operations risk" },
  @{ Name = "risk:customer-impact"; Color = "FBCA04"; Description = "Customer or acceptance impact" }
)

foreach ($label in $labels) {
  Ensure-Label -Name $label.Name -Color $label.Color -Description $label.Description
}

$milestones = @(
  "M1 - Docs Baseline",
  "M2 - Codebase Foundation",
  "M3 - Backend Core",
  "M4 - AI/ANSVIS Integration",
  "M5 - Web Portal",
  "M6 - Mobile App",
  "M7 - Integration & QA",
  "M8 - Security Hardening",
  "M9 - UAT & Go-live"
)

foreach ($milestone in $milestones) {
  Ensure-Milestone -Title $milestone
}

$existingIssuesJson = gh issue list --repo $repo --state all --limit 300 --json title
$existingIssues = $existingIssuesJson | ConvertFrom-Json
$script:ExistingIssueTitles = [System.Collections.Generic.HashSet[string]]::new()
foreach ($issue in $existingIssues) {
  $script:ExistingIssueTitles.Add([string]$issue.title) | Out-Null
}

$script:CreatedIssues = @()

$issues = @(
  @{
    Title = "[DOCS] Review and approve compact customer docs"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:docs,area:docs,priority:high"
    Body = "Review the compact customer-facing docs under `project-docs/docs-du-an-ai-camera/` and confirm the content is clear enough for boss/customer review.`n`nAcceptance:`n- Docs index is readable.`n- Scope is clear.`n- Security/privacy requirements are not weakened."
  },
  @{
    Title = "[DOCS] Review and approve implementation planning"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:docs,area:docs,priority:high"
    Body = "Review implementation planning under `implementation-planning/planning/`.`n`nAcceptance:`n- Phase plan is clear.`n- Security-first requirements are included.`n- Tooling requirements are clear."
  },
  @{
    Title = "[DOCS] Review AGENTS rules before coding"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:docs,area:docs,priority:high,risk:data-leak"
    Body = "Review root `AGENTS.md` and confirm agent/developer rules before coding.`n`nAcceptance:`n- Secret/data rules are clear.`n- ANSVIS/AI rules are included.`n- Verification rules are included."
  },
  @{
    Title = "[OPS] Configure GitHub Project board for boss tracking"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:ops,area:devops,priority:high"
    Body = "Create GitHub Project board based on `github-workflow/project-board-rules.md`.`n`nAcceptance:`n- Executive Overview view exists.`n- Security & Risk view exists.`n- Bug Tracking view exists.`n- Fields Phase/Type/Priority/Risk/Progress exist."
  },
  @{
    Title = "[OPS] Create labels and milestones in GitHub"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:ops,area:devops,priority:medium"
    Body = "Create GitHub labels and milestones based on `github-workflow/issue-labels-fields.md`.`n`nAcceptance:`n- Type labels exist.`n- Priority labels exist.`n- Area labels exist.`n- Risk labels exist.`n- Milestones M1-M9 exist."
  },
  @{
    Title = "[OPS] Initialize monorepo structure"
    Milestone = "M2 - Codebase Foundation"
    Labels = "type:ops,area:devops,priority:high"
    Body = "Initialize microservices-ready monorepo structure.`n`nExpected folders:`n- apps/`n- services/`n- workers/`n- packages/`n- infra/`n- docs/`n- scripts/`n`nAcceptance:`n- Folder structure follows AGENTS.md.`n- README explains structure."
  },
  @{
    Title = "[OPS] Add root .gitignore and .env.example policy"
    Milestone = "M2 - Codebase Foundation"
    Labels = "type:ops,area:security,priority:critical,risk:data-leak"
    Body = "Add root `.gitignore` and `.env.example` rules.`n`nAcceptance:`n- Real `.env` files are ignored.`n- Secret/key/license/dump/media/dataset paths are ignored.`n- Only placeholder `.env.example` is allowed."
  },
  @{
    Title = "[OPS] Add Docker Compose local stack"
    Milestone = "M2 - Codebase Foundation"
    Labels = "type:ops,area:devops,priority:high"
    Body = "Add local Docker Compose stack for development.`n`nServices:`n- PostgreSQL`n- Redis`n- RabbitMQ`n- MinIO`n`nAcceptance:`n- Stack starts locally.`n- No real secrets included.`n- README documents startup."
  },
  @{
    Title = "[SEC] Add secret scanning workflow"
    Milestone = "M2 - Codebase Foundation"
    Labels = "type:security,area:security,priority:critical"
    Body = "Add secret scanning workflow using gitleaks or equivalent.`n`nAcceptance:`n- Secret scan can run locally or in CI.`n- Scan fails on obvious fake secret pattern.`n- No real secret is committed."
  },
  @{
    Title = "[QA] Add baseline lint and test commands"
    Milestone = "M2 - Codebase Foundation"
    Labels = "type:qa,area:qa,priority:high"
    Body = "Add baseline lint/test commands after codebase scaffold.`n`nAcceptance:`n- Backend lint/test command documented.`n- Web/mobile lint/test command documented when scaffolded.`n- CI can call the commands."
  },
  @{
    Title = "[BE] Create API Gateway skeleton"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:high"
    Body = "Create API Gateway skeleton.`n`nAcceptance:`n- Health endpoint exists.`n- Request ID middleware exists.`n- Basic routing structure exists.`n- No business logic in gateway."
  },
  @{
    Title = "[BE] Create Identity Service skeleton"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:backend,priority:high,risk:permission"
    Body = "Create Identity Service skeleton for users, roles, permissions, sessions.`n`nAcceptance:`n- Service folder follows AGENTS.md.`n- Basic models/schemas planned.`n- Password/token rules documented."
  },
  @{
    Title = "[SEC] Implement RBAC and object-level authorization policy"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:security,priority:critical,risk:permission"
    Body = "Implement RBAC/ABAC and object-level authorization policy.`n`nAcceptance:`n- Parent can only access own child.`n- Teacher can only access assigned classes.`n- BGH/Admin scope is explicit.`n- Allowed/denied tests exist."
  },
  @{
    Title = "[BE] Create School Service schema"
    Milestone = "M3 - Backend Core"
    Labels = "type:feature,area:database,priority:high"
    Body = "Create School Service schema for student, parent, teacher, class, assignment.`n`nAcceptance:`n- PostgreSQL migration exists.`n- No real student data in seed/test.`n- Relations are explicit."
  },
  @{
    Title = "[SEC] Create Consent Service baseline"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:security,priority:critical,risk:biometric"
    Body = "Create Consent Service baseline for biometric/privacy consent.`n`nAcceptance:`n- Consent status can be checked.`n- Missing consent blocks biometric processing by default.`n- Consent changes are audited."
  },
  @{
    Title = "[SEC] Create append-only audit log baseline"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:security,priority:critical"
    Body = "Create append-only audit log baseline.`n`nAcceptance:`n- Sensitive view/export/update/delete actions can be audited.`n- Audit records include actor, action, target, timestamp, request ID.`n- No secret/biometric payload in audit log."
  },
  @{
    Title = "[AI] Define ANSVIS HTTP Trigger payload contract"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:ai,area:ansvis,priority:critical"
    Body = "Define minimal ANSVIS HTTP Trigger payload contract.`n`nAcceptance:`n- Required fields are documented.`n- Media policy is documented.`n- Payload avoids unnecessary base64/image data."
  },
  @{
    Title = "[AI] Build ANSVIS Adapter skeleton"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:ai,area:ansvis,priority:high"
    Body = "Build ANSVIS Adapter skeleton.`n`nAcceptance:`n- Webhook route exists.`n- Payload parser exists.`n- Normalized event model exists.`n- Raw ANSVIS fields do not leak into business services."
  },
  @{
    Title = "[SEC] Add ANSVIS webhook auth and source validation"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:security,area:ansvis,priority:critical"
    Body = "Add auth/source validation for ANSVIS webhook.`n`nAcceptance:`n- Token or HMAC validation exists.`n- Source validation policy exists.`n- Invalid requests are rejected and safely logged."
  },
  @{
    Title = "[AI] Add event idempotency rules"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:ai,area:backend,priority:critical"
    Body = "Add event idempotency rules for ANSVIS ingestion.`n`nAcceptance:`n- Duplicate event does not create duplicate attendance/violation/notification.`n- Idempotency key is documented and tested."
  },
  @{
    Title = "[AI] Add sanitized ANSVIS payload contract tests"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:qa,area:ansvis,priority:high"
    Body = "Add contract tests with sanitized ANSVIS payload fixtures.`n`nAcceptance:`n- No real camera/student/face data in fixtures.`n- Valid payload passes.`n- Invalid payload fails safely."
  },
  @{
    Title = "[AI] Define AI shadow mode and human review rules"
    Milestone = "M4 - AI/ANSVIS Integration"
    Labels = "type:ai,area:ai-model,priority:high,risk:customer-impact"
    Body = "Define AI shadow mode and human review rules.`n`nAcceptance:`n- Shadow mode behavior is documented.`n- Sensitive/low-confidence events require review.`n- Production enable criteria are clear."
  },
  @{
    Title = "[WEB] Create Web Portal skeleton"
    Milestone = "M5 - Web Portal"
    Labels = "type:feature,area:web,priority:high"
    Body = "Create Web Portal skeleton.`n`nAcceptance:`n- App starts locally.`n- Routing structure exists.`n- Auth guard placeholder exists.`n- No real data fixtures."
  },
  @{
    Title = "[MOB] Create React Native app skeleton"
    Milestone = "M6 - Mobile App"
    Labels = "type:feature,area:mobile,priority:high"
    Body = "Create React Native app skeleton.`n`nAcceptance:`n- App starts locally or in emulator.`n- Navigation structure exists.`n- Secure token storage approach is selected.`n- No real data fixtures."
  },
  @{
    Title = "[SEC] Add Web/Mobile route guard rules"
    Milestone = "M7 - Integration & QA"
    Labels = "type:security,area:security,priority:critical,risk:permission"
    Body = "Add route/screen guard rules for Web and Mobile.`n`nAcceptance:`n- Unauthorized screens are blocked.`n- Backend remains final authorization enforcement.`n- Tests cover allowed/denied access where applicable."
  },
  @{
    Title = "[QA] Define E2E test flow for attendance and violation"
    Milestone = "M7 - Integration & QA"
    Labels = "type:qa,area:qa,priority:high"
    Body = "Define E2E test flow for attendance and violation.`n`nAcceptance:`n- Login -> event -> attendance -> notification flow is covered.`n- Violation review flow is covered.`n- Tests use fake/sanitized data."
  },
  @{
    Title = "[OPS] Define backup and restore runbook"
    Milestone = "M8 - Security Hardening"
    Labels = "type:ops,area:devops,priority:critical,risk:production"
    Body = "Define backup and restore runbook.`n`nAcceptance:`n- PostgreSQL backup/restore is covered.`n- Object storage backup is covered.`n- ANSVIS config/model/face DB limitations are documented.`n- Restore test evidence requirement is defined."
  },
  @{
    Title = "[SEC] Define incident response runbook"
    Milestone = "M8 - Security Hardening"
    Labels = "type:security,area:security,priority:critical,risk:data-leak"
    Body = "Define incident response runbook for data leak/security events.`n`nAcceptance:`n- Detect, isolate, preserve evidence, fix, notify, postmortem steps exist.`n- Secret rotation rule exists.`n- School/parent notification decision path is documented."
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
