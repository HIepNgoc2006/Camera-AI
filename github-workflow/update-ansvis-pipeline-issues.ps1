$ErrorActionPreference = "Stop"

$Repo = "HIepNgoc2006/Camera-AI"

function Write-BodyFile {
    param(
        [string]$Path,
        [string]$Body
    )

    Set-Content -LiteralPath $Path -Value $Body -Encoding UTF8
}

$tmp = Join-Path $env:TEMP "camera-ai-github-issues"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

$body90 = @"
Create the mapping matrix for all 34 cameras and related ANSVIS AI tasks/pipelines.

Scope update:
- Current product scope has 6 functions grouped into 3 technical groups.
- Group 1: student attendance and staff timekeeping using shared Face Detection/Facial Recognition.
- Group 2: behavior violations using custom pipelines: Littering Detection and Smoking Detection.
- Group 3: uniform/PPE violations using custom pipelines: Student Uniform Detection and Kitchen PPE Detection.

Acceptance:
- 16 attendance/timekeeping/happiness cameras, 8 littering cameras, 8 smoking cameras and 2 kitchen/PPE cameras are represented.
- Each row has camera ID/name, location, ANSVIS task or custom pipeline, event type, ROI/line/zone, threshold, schedule and owner.
- The matrix identifies which functions use built-in ANSVIS models and which require custom pipeline/model/rule work.
- No physical installation task is added; this is software/integration mapping only.

Security/privacy impact:
- Face recognition cameras are marked biometric-critical.
- Violation evidence cameras are marked high sensitivity.
- No RTSP credentials, real student data, face images or camera secrets are stored in the issue.
"@

$body92 = @"
Define acceptance metrics for each AI model/pipeline.

Scope update:
- Facial Recognition is shared by student attendance and staff timekeeping.
- Four custom pipelines require separate acceptance criteria: Littering Detection, Smoking Detection, Student Uniform Detection, Kitchen PPE Detection.

Acceptance:
- Facial Recognition metrics cover false match, missed match, confidence threshold, low-confidence review and consent requirement.
- Littering Detection metrics cover false positive/false negative, object/person tracking, ROI, left-object rule and review workflow.
- Smoking Detection metrics cover suspected-smoking confidence, false positives with phone/pen/eating behavior, and mandatory human confirmation.
- Student Uniform Detection metrics cover agreed uniform classes/rules such as correct/incorrect uniform, student card, logo/color if required.
- Kitchen PPE Detection metrics cover hair cover, mask, apron, gloves, kitchen uniform and safety shoes as agreed.
- Human review thresholds and appeal/correction path are referenced.
- Metrics use approved camera/ANSVIS data only when real data is required.
"@

$bodyFace = @"
Configure and validate ANSVIS Face Detection/Facial Recognition for both student attendance and staff timekeeping.

Context:
- The current ANSVIS machine already has Face Detection and Facial Recognition models.
- Student attendance and staff timekeeping should share the same recognition foundation but use different backend business rules.

Acceptance:
- Face Detection and Facial Recognition model/task configuration is documented.
- Student and staff identity mapping approach is defined without exposing real face data in Git/issues.
- Backend event contract covers person type, person reference, confidence, camera, time, check-in/check-out event and low-confidence state.
- Attendance rules cover present, absent, late, check-in/check-out by class/schedule.
- Timekeeping rules cover shift, in/out, late, early leave and monthly summary.
- Consent gate is referenced for student biometric processing.
- Low-confidence or sensitive matches require human review.

Security/privacy impact:
- Biometric-critical.
- No face images, face DB export, real names or raw biometric payloads in repo/issues.
"@

$bodyLitter = @"
Design the Littering Detection custom pipeline for ANSVIS integration.

Context:
- Littering is a behavior pipeline, not simple single-frame object detection.
- It may use person detection, object/trash detection, object tracking, ROI and left-object logic.

Acceptance:
- Pipeline input/output event contract is defined.
- Required classes/signals are listed: person, candidate trash/object, ROI, track ID or equivalent.
- Rule logic is documented: object appears, person leaves, object remains outside allowed trash area.
- Allowed disposal zones and ignored zones are represented in camera/task mapping.
- Evidence policy is defined: image/video only when needed, private URL preferred, no base64 by default.
- False positive examples are listed: placing object temporarily, cleaning activity, dropped item picked up later.
- Shadow mode and human review rules are defined before production.

Security/privacy impact:
- Evidence media is high sensitivity.
- No real video/image sample in Git/issues.
"@

$bodySmoking = @"
Design the Smoking Detection custom pipeline for ANSVIS integration.

Context:
- Smoking detection is high-risk for false positives because cigarettes/vapes are small and hand-to-mouth gestures can look like phone, pen, food or drink.
- The system should return suspected smoking and require human confirmation for sensitive action.

Acceptance:
- Pipeline input/output event contract is defined.
- Required classes/signals are listed: cigarette/vape candidate, person, hand-to-mouth behavior, smoke signal if camera quality allows.
- Event wording uses suspected smoking, not final disciplinary conclusion.
- Human review is mandatory before escalation/disciplinary reporting.
- False positive examples are documented: phone, pen, eating, drinking, mask adjustment.
- Shadow mode metrics include false positive/false negative review.
- Evidence policy avoids unnecessary face crop/media exposure.

Security/privacy impact:
- Customer-impact high.
- Evidence media is high sensitivity.
- No real video/image sample in Git/issues.
"@

$bodyUniform = @"
Design the Student Uniform Detection custom pipeline for ANSVIS integration.

Context:
- Student uniform detection depends on the school's actual uniform policy.
- The pipeline must not be implemented until the accepted visual rules/classes are defined.

Acceptance:
- Uniform policy inputs are listed: shirt, trousers/skirt, student card, shoes, logo/color if required.
- Model/rule classes are proposed, e.g. person, uniform_correct, uniform_incorrect, student_card.
- ROI/camera angle assumptions are documented.
- Low-confidence or partial-visibility cases are routed to review instead of automatic conclusion.
- Event contract is defined for uniform status, confidence, missing component and evidence reference.
- Shadow mode and UAT acceptance criteria are defined.

Security/privacy impact:
- Student data and evidence media are high sensitivity.
- No real student images in Git/issues.
"@

$bodyPpe = @"
Design the Kitchen PPE Detection custom pipeline for ANSVIS integration.

Context:
- Kitchen uniform monitoring is a PPE/safety compliance problem.
- It should run only in kitchen-related camera zones and generate reviewable evidence.

Acceptance:
- PPE classes are confirmed: hair cover, mask, apron, gloves, kitchen uniform and safety shoes as agreed.
- Rule logic is documented: person in kitchen ROI and missing required PPE component triggers alert.
- Camera/ROI assumptions are listed.
- Event contract includes missing component, confidence, camera, time and evidence reference.
- Human review/correction path is defined.
- Shadow mode and acceptance metrics are defined before production.

Security/privacy impact:
- Staff evidence media is high sensitivity.
- No real kitchen/staff images in Git/issues.
"@

Write-BodyFile (Join-Path $tmp "issue-90.md") $body90
Write-BodyFile (Join-Path $tmp "issue-92.md") $body92
Write-BodyFile (Join-Path $tmp "issue-face.md") $bodyFace
Write-BodyFile (Join-Path $tmp "issue-litter.md") $bodyLitter
Write-BodyFile (Join-Path $tmp "issue-smoking.md") $bodySmoking
Write-BodyFile (Join-Path $tmp "issue-uniform.md") $bodyUniform
Write-BodyFile (Join-Path $tmp "issue-ppe.md") $bodyPpe

rtk gh issue edit 90 --repo $Repo --body-file (Join-Path $tmp "issue-90.md")
rtk gh issue edit 92 --repo $Repo --title "[AI] Define per-pipeline AI acceptance metrics" --body-file (Join-Path $tmp "issue-92.md")

rtk gh issue create --repo $Repo --title "[AI] Configure Facial Recognition for attendance and timekeeping" --body-file (Join-Path $tmp "issue-face.md") --label "type:ai,area:ansvis,priority:critical,risk:biometric" --milestone "M4 - AI/ANSVIS Integration"
rtk gh issue create --repo $Repo --title "[AI] Design Littering Detection custom pipeline" --body-file (Join-Path $tmp "issue-litter.md") --label "type:ai,area:ai-model,priority:high,risk:customer-impact" --milestone "M4 - AI/ANSVIS Integration"
rtk gh issue create --repo $Repo --title "[AI] Design Smoking Detection custom pipeline" --body-file (Join-Path $tmp "issue-smoking.md") --label "type:ai,area:ai-model,priority:high,risk:customer-impact" --milestone "M4 - AI/ANSVIS Integration"
rtk gh issue create --repo $Repo --title "[AI] Design Student Uniform Detection custom pipeline" --body-file (Join-Path $tmp "issue-uniform.md") --label "type:ai,area:ai-model,priority:high,risk:customer-impact" --milestone "M4 - AI/ANSVIS Integration"
rtk gh issue create --repo $Repo --title "[AI] Design Kitchen PPE Detection custom pipeline" --body-file (Join-Path $tmp "issue-ppe.md") --label "type:ai,area:ai-model,priority:high,risk:customer-impact" --milestone "M4 - AI/ANSVIS Integration"

rtk gh issue list --repo $Repo --state open --limit 120 --json number,title,labels,milestone
