# Requirements, docs and issues traceability audit

## Mục tiêu

File này kiểm tra độ khớp giữa:

1. Yêu cầu khách hàng/project docs trong `project-docs/docs-du-an-ai-camera/`.
2. Planning nội bộ trong `implementation-planning/planning/`.
3. GitHub Issues trong repo `HIepNgoc2006/Camera-AI`.

Mục tiêu là bảo đảm trước khi code, các yêu cầu chính đều có tài liệu, plan và issue theo dõi.

## Kết luận

Sau khi đối chiếu và cập nhật theo hướng ANSVIS-first, hệ thống **đã có coverage phần lớn** giữa docs, planning và GitHub Issues. Coverage không đồng nghĩa execution-ready: requirement chỉ được coi là `Ready` khi artifact/decision, dependency, acceptance, test và evidence tương ứng đã tồn tại.

Điểm đã khóa lại sau khi xem video AIBOX/ANSVIS:

- Web/App/Backend được build bằng mock/sanitized ANSVIS event, không chờ train AI.
- ANSVIS Integration là workstream riêng: HTTP Trigger, Adapter, event contract, camera/task health.
- AI pipeline/training là workstream riêng: Facial Recognition dùng model có sẵn; Littering, Smoking, Student Uniform, Kitchen PPE đi qua spec/baseline/shadow; train/fine-tune chỉ khi cần.
- GitHub Issues #17, #18, #22, #90 và #92 đã được cập nhật để phản ánh hướng này.

Các gap nội dung chính đã có issue theo dõi, bao gồm issue #97 duy trì traceability và các issue #98-#102 cho Facial Recognition cùng bốn custom pipelines. Phần còn phải khóa trước business code là chất lượng thực thi của backlog: dependency tuần tự, Definition of Done/evidence, mapping Student Uniform vào nhóm camera phù hợp, role/permission matrix và API/event contract có artifact kiểm chứng được.

## Traceability matrix

| Yêu cầu / phạm vi | Customer docs | Planning docs | GitHub issue coverage | Trạng thái |
|---|---|---|---|---|
| 34 camera theo nhóm nghiệp vụ | `product-scope-requirements.md` | `ai-ansvis-plan.md`, `system-master-plan.md` | #30, #60, #90 | Có issue; cần khóa mapping Student Uniform |
| Không làm phần cứng/lắp đặt | `product-scope-requirements.md`, `docs-index.md` | `system-master-plan.md`, `AGENTS.md` | #1, #2, #3 | Khớp |
| Điểm danh học sinh | `product-scope-requirements.md`, `business-event-flows.md` | `architecture-stack.md`, `ai-ansvis-plan.md` | #17, #20, #21, #22, #61, #62, #72, #82 | Khớp |
| Chấm công cán bộ/giáo viên | `product-scope-requirements.md`, `business-event-flows.md` | `architecture-stack.md` | #63, #66, #88 | Khớp cơ bản |
| Vi phạm đồng phục/đi trễ/xả rác/hút thuốc/bảo hộ bếp | `product-scope-requirements.md`, `business-event-flows.md` | `ai-ansvis-plan.md`, `architecture-stack.md` | #64, #73, #84, #99, #100, #101, #102, #92 | Đã cập nhật theo 4 custom pipeline |
| Happiness index | Một số tài liệu cũ còn đề cập | `planning-index.md`, `workstream-implementation-plan.md` | #91 | Optional/Future Scope; không thuộc baseline hiện tại |
| Web Portal cho BGH/Admin/GV/Phụ huynh | `product-scope-requirements.md`, `ui-web-mobile.md` | `architecture-stack.md`, `coding-agent-rules.md` | #23, #70-#78, #93, #94 | Khớp |
| Mobile App React Native | `product-scope-requirements.md`, `ui-web-mobile.md` | `architecture-stack.md`, `coding-agent-rules.md` | #24, #36, #79-#87 | Khớp |
| Vai trò Admin/BGH/GV/Phụ huynh/Bếp/Vận hành/Auditor | `product-scope-requirements.md` | `security-privacy-plan.md`, `coding-agent-rules.md` | #12, #13, #15, #16, #70, #75, #76, #85 | Có baseline fail-closed; chờ khách hàng xác nhận các quyền evidence/correction/export |
| ANSVIS/AIBOX HTTP Trigger | `business-event-flows.md`, `ai-ansvis-security-privacy.md` | `ai-ansvis-plan.md` | #17, #18, #19, #20, #21, #45 | Khớp |
| Facial Recognition dùng chung cho điểm danh/chấm công | `ai-ansvis-security-privacy.md`, `business-event-flows.md` | `ai-ansvis-plan.md` | #98 | Đã bổ sung |
| 4 custom AI pipelines | `ai-ansvis-security-privacy.md` | `ai-ansvis-plan.md` | #99 Littering, #100 Smoking, #101 Student Uniform, #102 Kitchen PPE | Đã bổ sung |
| ANSVIS license/GPU/capacity | `testing-acceptance-risk.md` | `risk-assessment.md`, `ai-ansvis-plan.md` | #30, #95, #96 | Khớp về kế hoạch; chờ xác minh môi trường thật |
| PostgreSQL database chính | `technical-architecture-data-api.md` | `architecture-stack.md`, `database-and-encryption-plan.md` | #14, #47-#58, #67, #69 | Khớp |
| Mã hóa dữ liệu/key management | `technical-architecture-data-api.md`, `ai-ansvis-security-privacy.md` | `database-and-encryption-plan.md`, `security-privacy-plan.md` | #47, #50, #51, #55, #57 | Khớp |
| Consent biometric | `product-scope-requirements.md`, `ai-ansvis-security-privacy.md` | `security-privacy-plan.md`, `database-and-encryption-plan.md` | #15, #33, #49, #54, #76, #85 | Khớp |
| Audit log | `technical-architecture-data-api.md`, `testing-acceptance-risk.md` | `database-and-encryption-plan.md`, `security-privacy-plan.md` | #16, #31, #53, #67 | Khớp |
| Evidence storage/signed URL | `business-event-flows.md`, `technical-architecture-data-api.md` | `database-and-encryption-plan.md`, `risk-assessment.md` | #31, #52, #67, #73, #84 | Khớp |
| Notification đúng người, không lộ dữ liệu | `product-scope-requirements.md`, `testing-acceptance-risk.md` | `risk-assessment.md`, `coding-agent-rules.md` | #32, #65, #83, #86 | Khớp |
| Report/export có audit | `technical-architecture-data-api.md`, `testing-acceptance-risk.md` | `database-and-encryption-plan.md` | #38, #66, #74 | Khớp |
| Security/DDoS/webhook flood | `testing-acceptance-risk.md` | `risk-assessment.md`, `security-privacy-plan.md` | #44, #45, #46, #89 | Khớp |
| Backup/restore/runbook | `operations-handover-runbook.md`, `testing-acceptance-risk.md` | `operations-tracking-plan.md`, `database-and-encryption-plan.md` | #27, #34, #42, #55 | Khớp |
| QA/UAT/acceptance | `testing-acceptance-risk.md` | `delivery-quality-plan.md`, `pre-code-readiness-audit.md` | #10, #21, #26, #38, #43, #46, #57, #88, #89, #103 | Khớp về coverage; chờ evidence |
| Deployment architecture/performance | `technical-architecture-data-api.md` | `architecture-stack.md`, `tooling-requirements.md`, `risk-assessment.md` | #8, #30, #41, #56, #95, #96 | Khớp |
| Go-live, đào tạo, bàn giao, rollback, support | `operations-handover-runbook.md`, `testing-acceptance-risk.md` | `system-master-plan.md`, `delivery-quality-plan.md`, `operations-tracking-plan.md` | #27, #28, #34, #88, #89, #96, #103 | Đã có issue tổng hợp #103; chỉ đạt khi có sign-off/evidence |

## Requirement readiness register

| Requirement ID | Requirement/gate | Artifact/decision cần có | Issue owner | Chặn |
|---|---|---|---|---|
| REQ-SEC-01 | Phân quyền theo role và object | Ma trận quyền được khách hàng xác nhận, policy + allowed/denied tests | #13 | API dữ liệu học sinh, Web/Mobile |
| REQ-PRIV-01 | Consent trước biometric | Purpose, subject/guardian authority, withdrawal, retention/delete rule | #15, #33, #54 | Facial Recognition và lưu face data |
| REQ-API-01 | API contract ổn định | OpenAPI, error schema, auth/audit annotations | #59 | Backend client, Web, Mobile |
| REQ-INT-01 | ANSVIS event contract tối thiểu | Versioned normalized schema, auth/size/media policy, sanitized fixtures | #17, #19, #21 | Adapter, ingestion, business event flow |
| REQ-DATA-01 | Schema và mã hóa theo field | ERD/data dictionary, field classification, encryption/key/audit/retention rules | #48-#54 | Migration và repository code |
| REQ-AI-01 | Mapping 34 camera/task | Sanitized mapping camera/task/ROI/schedule/owner/status | #90 | Capacity benchmark và 4 custom pipelines |
| REQ-AI-02 | AI acceptance định lượng | Metric/threshold, shadow/human-review/appeal/rollback rule | #22, #92, #99-#102 | AI production acceptance |
| REQ-OPS-01 | Go-live và bàn giao an toàn | UAT, production gate, training, handover, backup/rollback/support evidence | #27, #28, #34, #88, #89, #96, #103 | Production go-live |

## Các điểm không được coi là lệch

| Điểm | Lý do |
|---|---|
| Không có issue khảo sát/lắp đặt camera | Đúng phạm vi: team chỉ làm phần mềm |
| Không có timeline ngày giờ chi tiết | User đã xác nhận thời gian đàm phán sau |
| Một số issue là module lớn | Chấp nhận ở giai đoạn planning; khi code có thể tách subtask 1-3 ngày |
| ANSVIS xử lý camera chính thay vì backend đọc trực tiếp RTSP | Khớp với hướng tài liệu ANSCENTER/ANSVIS |

## Issue kiểm soát gap hiện tại

| Gap | Issue theo dõi |
|---|---|
| 34 camera cần khóa mapping matrix | #90 `[AI] Define 34-camera task mapping matrix` |
| Happiness index cần tách khỏi baseline | #91 `[AI] Define happiness index scope and privacy guardrails` |
| Per-pipeline metric chưa rõ | #92 `[AI] Define per-pipeline AI acceptance metrics` |
| Facial Recognition dùng chung chưa có issue rõ | #98 `[AI] Configure Facial Recognition for attendance and timekeeping` |
| Littering custom pipeline chưa có issue riêng | #99 `[AI] Design Littering Detection custom pipeline` |
| Smoking custom pipeline chưa có issue riêng | #100 `[AI] Design Smoking Detection custom pipeline` |
| Student Uniform custom pipeline chưa có issue riêng | #101 `[AI] Design Student Uniform Detection custom pipeline` |
| Kitchen PPE custom pipeline chưa có issue riêng | #102 `[AI] Design Kitchen PPE Detection custom pipeline` |
| Parent Web Portal | #93 `[WEB] Build parent portal view` |
| Teacher Web view | #94 `[WEB] Build teacher class view` |
| 34-camera performance benchmark | #95 `[QA] Define 34-camera performance benchmark plan` |
| Deployment/capacity baseline | #96 `[OPS] Define deployment architecture and capacity baseline` |
| Duy trì traceability | #97 `[DOCS] Maintain requirements-to-issues traceability matrix` |
| Role/object permission matrix cần xác nhận | #13 `[SEC] Implement RBAC and object-level authorization policy` |
| OpenAPI và normalized event contract cần artifact | #59, #17, #21 |
| Go-live/đào tạo/bàn giao/rollback chưa có tracker tổng hợp | #103 `[OPS] Prepare go-live training and handover package` |

## Kết luận hành động

Cho phép tiếp tục repository/codebase foundation bằng fake data. Trước business code, phải khóa dependency cho các issue Critical/High và hoàn thiện artifact/evidence của REQ-SEC-01, REQ-API-01, REQ-INT-01 và REQ-DATA-01. Trước pilot/production, phải hoàn thiện REQ-PRIV-01, REQ-AI-01, REQ-AI-02 và REQ-OPS-01. Không tạo thêm planning/issue nếu không xuất hiện requirement hoặc gate mới.
