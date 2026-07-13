$ErrorActionPreference = "Stop"

$repo = "HIepNgoc2006/Camera-AI"

function Update-IssueBody {
  param(
    [Parameter(Mandatory = $true)][int]$Number,
    [Parameter(Mandatory = $true)][string]$Body
  )

  $tmpPath = [System.IO.Path]::GetTempFileName()
  try {
    Set-Content -LiteralPath $tmpPath -Value $Body -Encoding UTF8
    rtk gh issue edit $Number --repo $repo --body-file $tmpPath
  }
  finally {
    Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
  }
}

Update-IssueBody -Number 17 -Body @"
Define minimal ANSVIS HTTP Trigger payload contract.

Context:
- ANSVIS/AIBOX is the main video analytics layer.
- Backend/Web/Mobile must not depend on raw ANSVIS payload fields.
- Product Platform should be buildable with mock/sanitized event before real camera/model output is available.

Acceptance:
- Required event fields are documented: schema_version, event_id/idempotency key, event_type, camera_id, task_id, event_time, confidence, ROI/zone, model/config version when available.
- Six business event groups are covered: face attendance/timekeeping, littering, suspected smoking, student uniform, kitchen PPE and camera/task health.
- Media policy is documented: private media URL/signed URL preferred; no base64 by default.
- Payload avoids unnecessary biometric/media data.
- Payload examples are sanitized and safe to commit.
- Contract explicitly separates ANSVIS raw payload from internal normalized event schema.

Security/privacy impact:
- Webhook payload may reference biometric/evidence data.
- No real ANSVIS payload, RTSP URL, face image, face DB, token or camera credential in Git/issues.
"@

Update-IssueBody -Number 18 -Body @"
Build ANSVIS Adapter skeleton.

Context:
- ANSVIS Integration is a separate workstream from Product Platform and AI training.
- The adapter is the only layer that understands ANSVIS-specific payload shape.

Acceptance:
- Webhook route exists.
- Payload parser and validator exist.
- Normalized event model exists for attendance/timekeeping, violation and camera/task health events.
- Raw ANSVIS fields do not leak into business services, Web or Mobile.
- Adapter supports idempotency handoff and safe error response shape.
- Mock/sanitized fixtures allow Backend/Web/Mobile E2E development without real camera/model output.
- Debug/raw payload logging is disabled by default.

Security/privacy impact:
- Reject invalid source/auth/schema/size.
- Mask tokens, RTSP credentials, face/media/base64 and raw biometric payload in logs.
"@

Update-IssueBody -Number 22 -Body @"
Define AI shadow mode and human review rules.

Context:
- Facial Recognition can be configured using existing ANSVIS Face Detection/Facial Recognition.
- Four custom pipelines require separate validation: Littering Detection, Smoking Detection, Student Uniform Detection and Kitchen PPE Detection.
- Training/fine-tune is conditional, only after baseline/shadow mode shows model/rule gaps.

Acceptance:
- Shadow mode behavior is documented: event recorded for evaluation but no automatic disciplinary conclusion.
- Sensitive/low-confidence events require human review.
- Smoking event wording uses suspected smoking.
- Littering is evaluated as behavior, not single-frame garbage detection.
- Uniform/PPE decisions include unknown/partial-visibility handling.
- Production enable criteria are clear per pipeline.
- Rollback/disable path exists per model/config/task.

Security/privacy impact:
- Evidence media is high sensitivity.
- No real student/staff image/video sample in Git/issues.
"@

Update-IssueBody -Number 90 -Body @"
Create the mapping matrix for all 34 cameras and related ANSVIS AI tasks/pipelines.

Scope update:
- Current product scope has 6 functions grouped into 3 technical groups.
- Group 1: student attendance and staff timekeeping using shared Face Detection/Facial Recognition.
- Group 2: behavior violations using custom pipelines: Littering Detection and Smoking Detection.
- Group 3: uniform/PPE violations using custom pipelines: Student Uniform Detection and Kitchen PPE Detection.
- Web/App/Backend must be able to work with mock/sanitized event before all real AI pipelines are production-ready.

Acceptance:
- 16 attendance/timekeeping cameras, 8 littering cameras, 8 smoking cameras and 2 kitchen/PPE cameras are represented.
- Student Uniform is explicitly mapped to suitable cameras in the existing 34-camera allocation; no additional physical camera is assumed.
- Each row has camera ID/name, location, ANSVIS task or custom pipeline, event type, ROI/line/zone, threshold, schedule and owner.
- The matrix identifies which functions use built-in ANSVIS models and which require custom pipeline/model/rule work.
- The matrix tracks status: planned, configured, baseline, shadow, accepted, production, disabled.
- No physical installation task is added; this is software/integration mapping only.

Security/privacy impact:
- Face recognition cameras are marked biometric-critical.
- Violation evidence cameras are marked high sensitivity.
- No RTSP credentials, real student data, face images or camera secrets are stored in the issue.

Dependencies:
- Blocked by: None for draft mapping.
- Production lock requires #30 ANSVIS license/task/GPU verification and the sanitized camera inventory supplied by the responsible party.
- Blocks: #95, #99, #100, #101 and #102.
"@

Update-IssueBody -Number 92 -Body @"
Define acceptance metrics for each AI model/pipeline.

Scope update:
- Facial Recognition is shared by student attendance and staff timekeeping.
- Four custom pipelines require separate acceptance criteria: Littering Detection, Smoking Detection, Student Uniform Detection, Kitchen PPE Detection.
- Model training/fine-tune is not assumed upfront; metrics must first cover baseline/shadow mode using current ANSVIS models/rules where possible.

Acceptance:
- Facial Recognition metrics cover false match, missed match, confidence threshold, low-confidence review and consent requirement.
- Littering Detection metrics cover false positive/false negative, object/person tracking, ROI, left-object rule and review workflow.
- Smoking Detection metrics cover suspected-smoking confidence, false positives with phone/pen/eating behavior, and mandatory human confirmation.
- Student Uniform Detection metrics cover agreed uniform classes/rules such as correct/incorrect uniform, student card, logo/color if required.
- Kitchen PPE Detection metrics cover hair cover, mask, apron, gloves, kitchen uniform and safety shoes as agreed.
- Human review thresholds and appeal/correction path are referenced.
- Metrics use approved camera/ANSVIS data only when real data is required.
- Acceptance distinguishes baseline, shadow, training-needed and production-ready states.
"@

Update-IssueBody -Number 91 -Body @"
Classify happiness index as Optional/Future Scope.

Context:
- The current implementation baseline contains six functions only: student attendance, staff timekeeping, littering, suspected smoking, student uniform and kitchen PPE.
- Happiness index is not required for the current baseline and must not block Product Platform, ANSVIS Integration or the four custom pipelines.

Acceptance:
- Issue is documented as optional/future scope, not an active implementation dependency.
- No model, dataset, UI, API or database work is started under the current baseline.
- Any future activation requires a separate change request, stated purpose, privacy impact assessment, consent/legal basis, acceptance metrics and human-review policy.
- It must not be used for individual psychological assessment, discipline or high-impact automated decisions.

Dependencies:
- Blocked by: a future approved change request; no dependency in the current baseline.

Security/privacy impact:
- Emotion or inferred-state analytics involving children is high risk and remains disabled by default.
"@

Update-IssueBody -Number 99 -Body @"
Design and validate the Littering Detection custom pipeline.

Pipeline checklist:
- [ ] Define person/object classes, trash zones, allowed disposal zones, left-object behavior and human-review rule.
- [ ] Verify applicable built-in ANSVIS models/classes and record the installed version.
- [ ] Run baseline using person/object detection, tracking, ROI and rule configuration.
- [ ] Version ROI, threshold, tracker, schedule and event payload mapping.
- [ ] Run shadow mode with approved project-camera samples.
- [ ] Measure precision, recall, false positive, false negative, latency and evidence quality.
- [ ] Test confusing cases: temporary object placement, cleaning, picking up objects and accidental drops.
- [ ] Create dataset manifest/labels and train or fine-tune only if baseline misses the agreed threshold.
- [ ] Register dataset hash, model/config version, metrics and reviewer.
- [ ] Import candidate into ANSVIS, repeat shadow mode, complete acceptance and verify rollback/disable.

Acceptance:
- Littering is evaluated as a behavior pipeline, not a single-frame garbage class.
- No automatic disciplinary conclusion is produced without evidence and human review.
- Sanitized event contract is compatible with the ANSVIS Adapter.
- No real dataset, image, video, RTSP credential or ANSVIS secret is committed to Git or issue comments.

Dependencies:
- Blocked by: #90 camera/task mapping and #92 per-pipeline metrics.
- Integration contract depends on #17 and #18.
"@

Update-IssueBody -Number 100 -Body @"
Design and validate the Smoking Detection custom pipeline.

Pipeline checklist:
- [ ] Define cigarette/vape candidates, hand-to-mouth temporal behavior, optional smoke signal and human-review rule.
- [ ] Verify applicable built-in ANSVIS models/classes and record the installed version.
- [ ] Run baseline using object/person detection, tracking, ROI and temporal rules.
- [ ] Version ROI, threshold, tracker, schedule and event payload mapping.
- [ ] Run shadow mode with approved project-camera samples.
- [ ] Measure precision, recall, false positive, false negative, latency and evidence quality.
- [ ] Test confusing cases: phone, pen, eating, drinking and mask adjustment.
- [ ] Create dataset manifest/labels and train or fine-tune only if baseline misses the agreed threshold.
- [ ] Register dataset hash, model/config version, metrics and reviewer.
- [ ] Import candidate into ANSVIS, repeat shadow mode, complete acceptance and verify rollback/disable.

Acceptance:
- Output wording is suspected smoking and requires human confirmation.
- No automatic disciplinary conclusion is produced from a low-confidence event.
- Sanitized event contract is compatible with the ANSVIS Adapter.
- No real dataset, image, video, RTSP credential or ANSVIS secret is committed to Git or issue comments.

Dependencies:
- Blocked by: #90 camera/task mapping and #92 per-pipeline metrics.
- Integration contract depends on #17 and #18.
"@

Update-IssueBody -Number 101 -Body @"
Design and validate the Student Uniform Detection custom pipeline.

Pipeline checklist:
- [ ] Obtain the explicit uniform policy: garments, colors, logo, student card, footwear and exceptions.
- [ ] Map Student Uniform to suitable cameras inside the existing 34-camera allocation.
- [ ] Verify applicable built-in ANSVIS models/classes and record the installed version.
- [ ] Run baseline using person detection, ROI and component/rule evaluation.
- [ ] Define correct, incorrect, unknown and partial-visibility outputs.
- [ ] Version ROI, threshold, schedule and event payload mapping.
- [ ] Run shadow mode and measure precision, recall, FP/FN, latency and evidence quality.
- [ ] Create dataset manifest/labels and train or fine-tune only if baseline misses the agreed threshold.
- [ ] Register dataset hash, model/config version, metrics and reviewer.
- [ ] Import candidate into ANSVIS, repeat shadow mode, complete acceptance and verify rollback/disable.

Acceptance:
- The pipeline follows the documented school uniform policy and handles occlusion/unknown safely.
- No automatic disciplinary conclusion is produced without human review.
- Sanitized event contract is compatible with the ANSVIS Adapter.
- No real dataset, image, video, RTSP credential or ANSVIS secret is committed to Git or issue comments.

Dependencies:
- Blocked by: #90 camera/task mapping and #92 per-pipeline metrics.
- Integration contract depends on #17 and #18.
"@

Update-IssueBody -Number 102 -Body @"
Design and validate the Kitchen PPE Detection custom pipeline.

Pipeline checklist:
- [ ] Confirm required PPE components: hair cover, mask, apron, gloves, kitchen uniform and safety shoes.
- [ ] Define kitchen-only ROI, missing-component rules, unknown/partial-visibility outputs and human-review rule.
- [ ] Verify applicable built-in ANSVIS person/helmet/object models and record the installed version.
- [ ] Run baseline using person detection, ROI and component/rule evaluation.
- [ ] Version ROI, threshold, schedule and event payload mapping.
- [ ] Run shadow mode and measure precision, recall, FP/FN, latency and evidence quality.
- [ ] Test occlusion, multiple workers, temporary removal and visitors/non-kitchen staff.
- [ ] Create dataset manifest/labels and train or fine-tune only if baseline misses the agreed threshold.
- [ ] Register dataset hash, model/config version, metrics and reviewer.
- [ ] Import candidate into ANSVIS, repeat shadow mode, complete acceptance and verify rollback/disable.

Acceptance:
- Detection runs only in the agreed kitchen ROI and reports the missing PPE component.
- Unknown or partially visible cases are not treated as confirmed violations automatically.
- Sanitized event contract is compatible with the ANSVIS Adapter.
- No real dataset, image, video, RTSP credential or ANSVIS secret is committed to Git or issue comments.

Dependencies:
- Blocked by: #90 camera/task mapping and #92 per-pipeline metrics.
- Integration contract depends on #17 and #18.
"@

Write-Output "ANSVIS-first issue sync completed."
