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
    Title = "[DBSEC] Complete database and encryption plan"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:docs,area:database,area:security,priority:critical,risk:data-leak"
    Body = "Finalize the database and encryption planning baseline before database coding starts.`n`nReference:`n- implementation-planning/planning/database-and-encryption-plan.md`n`nAcceptance:`n- PostgreSQL schema strategy is documented.`n- Encryption, key management, backup, retention, audit and go-live gates are documented.`n- AGENTS/planning index point to the file."
  },
  @{
    Title = "[DBSEC] Design ERD and data dictionary"
    Milestone = "M3 - Backend Core"
    Labels = "type:docs,area:database,priority:critical"
    Body = "Create ERD and data dictionary for the core PostgreSQL schemas.`n`nAcceptance:`n- Tables, fields, primary keys, foreign keys and indexes are listed.`n- Owner domain/service is clear for each table.`n- JSONB use is justified and controlled."
  },
  @{
    Title = "[DBSEC] Classify data by table and field"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:database,priority:critical,risk:data-leak,risk:biometric"
    Body = "Classify sensitive data by table and field before implementation.`n`nAcceptance:`n- PII, biometric, evidence, event, secret metadata and audit data are identified.`n- Required handling is defined for each sensitive field.`n- Unknown fields default to higher sensitivity."
  },
  @{
    Title = "[DBSEC] Define application-level encryption rules"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:security,area:database,priority:critical,risk:data-leak"
    Body = "Define application-level encryption rules for critical data.`n`nAcceptance:`n- Fields requiring encryption are listed.`n- key_id and envelope encryption approach are defined.`n- HMAC/hash lookup approach is defined for searchable encrypted values.`n- Encryption does not replace authorization."
  },
  @{
    Title = "[DBSEC] Define key management and rotation plan"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:security,priority:critical,risk:data-leak"
    Body = "Define key management, rotation, revoke and recovery plan.`n`nAcceptance:`n- Secret manager/KMS strategy is documented.`n- Production keys are not stored in Git/database business tables.`n- Rotation and revoke procedures are defined.`n- Recovery and audit requirements are defined."
  },
  @{
    Title = "[DBSEC] Define object storage evidence policy"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:database,priority:critical,risk:data-leak"
    Body = "Define object storage policy for evidence image/video.`n`nAcceptance:`n- PostgreSQL stores metadata only, not binary/base64 media.`n- Bucket must be private and encrypted.`n- Signed URL TTL and access audit are required.`n- Push notification must not include signed evidence URL."
  },
  @{
    Title = "[DBSEC] Design audit log schema"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:database,priority:critical"
    Body = "Design audit log schema for sensitive actions.`n`nAcceptance:`n- Audit events include actor, action, resource, result, timestamp and request_id.`n- Sensitive view/export/update/delete actions are covered.`n- Audit log does not copy full PII/biometric/raw payload unnecessarily."
  },
  @{
    Title = "[DBSEC] Define retention delete and anonymize policy"
    Milestone = "M3 - Backend Core"
    Labels = "type:security,area:database,priority:critical,risk:biometric"
    Body = "Define retention, delete and anonymize policy by data type.`n`nAcceptance:`n- Retention matrix exists for biometric, attendance, violation evidence, notification, export, logs and backups.`n- Consent withdrawal behavior is defined.`n- Retention job requires dry-run, audit and approval where needed."
  },
  @{
    Title = "[DBSEC] Define encrypted backup and restore drill"
    Milestone = "M8 - Security Hardening"
    Labels = "type:ops,area:devops,area:database,priority:critical,risk:production"
    Body = "Define encrypted backup and restore drill for PostgreSQL/object storage/model artifacts.`n`nAcceptance:`n- Backup encryption is required.`n- Restore test into a non-production environment is required.`n- RPO/RTO, access control and verification steps are documented.`n- ANSVIS backup limitations are referenced."
  },
  @{
    Title = "[DBSEC] Define database hardening checklist"
    Milestone = "M8 - Security Hardening"
    Labels = "type:security,area:database,priority:high,risk:production"
    Body = "Define database hardening checklist before staging/production.`n`nAcceptance:`n- PostgreSQL is not public internet exposed.`n- Runtime app account is least privilege and not superuser.`n- TLS, firewall/private network, backup, monitoring and migration review are covered.`n- No real seed/dump files are allowed in repo."
  },
  @{
    Title = "[DBSEC] Define database encryption test matrix"
    Milestone = "M7 - Integration & QA"
    Labels = "type:qa,area:qa,area:database,priority:high"
    Body = "Define test matrix for database and encryption behavior.`n`nAcceptance:`n- Migration apply/rollback tests are defined.`n- Encryption/decryption/key rotation tests are defined.`n- Permission/object-level authorization, consent, retention, evidence access, backup/restore and log masking tests are defined."
  },
  @{
    Title = "[DBSEC] Sync DBSEC issues with GitHub project"
    Milestone = "M1 - Docs Baseline"
    Labels = "type:ops,area:devops,priority:medium"
    Body = "Sync DBSEC issue group with GitHub tracking.`n`nAcceptance:`n- DBSEC issues exist on GitHub.`n- Labels and milestones are assigned.`n- Issues can be added to the boss tracking project board."
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