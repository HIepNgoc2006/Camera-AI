# Initial GitHub issues backlog

Danh sách này dùng để tạo issue ban đầu lên repo:

```text
https://github.com/HIepNgoc2006/Camera-AI
```

Ưu tiên tạo theo thứ tự từ trên xuống. Không cần tạo hết một lần nếu muốn giữ board gọn.

## M1 - Docs Baseline

| Title | Labels | Priority | Notes |
|---|---|---|---|
| `[DOCS] Review and approve compact customer docs` | `type:docs`, `area:docs`, `priority:high` | High | Kiểm bộ `project-docs` compact |
| `[DOCS] Review and approve implementation planning` | `type:docs`, `area:docs`, `priority:high` | High | Kiểm bộ `implementation-planning` |
| `[DOCS] Review AGENTS rules before coding` | `type:docs`, `area:docs`, `priority:high`, `risk:data-leak` | High | Bắt buộc trước coding |
| `[OPS] Configure GitHub Project board for boss tracking` | `type:ops`, `area:devops`, `priority:high` | High | Tạo views/fields theo folder này |
| `[OPS] Create labels and milestones in GitHub` | `type:ops`, `area:devops`, `priority:medium` | Medium | Theo `issue-labels-fields.md` |

## M2 - Codebase Foundation

| Title | Labels | Priority | Notes |
|---|---|---|---|
| `[OPS] Initialize monorepo structure` | `type:ops`, `area:devops`, `priority:high` | High | apps/services/workers/packages/infra/docs |
| `[OPS] Add root .gitignore and .env.example policy` | `type:ops`, `area:security`, `priority:critical`, `risk:data-leak` | Critical | Chặn secret/media/dataset |
| `[OPS] Add Docker Compose local stack` | `type:ops`, `area:devops`, `priority:high` | High | PostgreSQL, Redis, RabbitMQ, MinIO |
| `[SEC] Add secret scanning workflow` | `type:security`, `area:security`, `priority:critical` | Critical | gitleaks |
| `[QA] Add baseline lint and test commands` | `type:qa`, `area:qa`, `priority:high` | High | ruff/pytest/eslint sau khi scaffold |

## M3 - Backend Core

| Title | Labels | Priority | Notes |
|---|---|---|---|
| `[BE] Create API Gateway skeleton` | `type:feature`, `area:backend`, `priority:high` | High | Entry point |
| `[BE] Create Identity Service skeleton` | `type:feature`, `area:backend`, `priority:high`, `risk:permission` | High | User/role/session |
| `[SEC] Implement RBAC and object-level authorization policy` | `type:security`, `area:security`, `priority:critical`, `risk:permission` | Critical | Không được bỏ qua |
| `[BE] Create School Service schema` | `type:feature`, `area:database`, `priority:high` | High | student/parent/teacher/class |
| `[SEC] Create Consent Service baseline` | `type:security`, `area:security`, `priority:critical`, `risk:biometric` | Critical | Chặn biometric nếu thiếu consent |
| `[SEC] Create append-only audit log baseline` | `type:security`, `area:security`, `priority:critical` | Critical | Xem/sửa/xóa/export |

## M3 - Database security and encryption

Nhóm issue này phải được xử lý trước khi dùng dữ liệu thật hoặc triển khai production. Nội dung chi tiết nằm trong `implementation-planning/planning/database-and-encryption-plan.md`.

| Title | Labels | Priority | Notes |
|---|---|---|---|
| `[DBSEC] Complete database and encryption plan` | `type:docs`, `area:database`, `area:security`, `priority:critical`, `risk:data-leak` | Critical | Chốt nguồn chuẩn cho DB/encryption |
| `[DBSEC] Design ERD and data dictionary` | `type:docs`, `area:database`, `priority:critical` | Critical | Bảng, field, khóa, quan hệ, index |
| `[DBSEC] Classify data by table and field` | `type:security`, `area:database`, `priority:critical`, `risk:data-leak`, `risk:biometric` | Critical | Field-level classification |
| `[DBSEC] Define application-level encryption rules` | `type:security`, `area:security`, `area:database`, `priority:critical`, `risk:data-leak` | Critical | Field mã hóa, `key_id`, lookup hash |
| `[DBSEC] Define key management and rotation plan` | `type:security`, `area:security`, `priority:critical`, `risk:data-leak` | Critical | Secret manager/KMS, rotate, revoke |
| `[DBSEC] Define object storage evidence policy` | `type:security`, `area:database`, `priority:critical`, `risk:data-leak` | Critical | Private bucket, signed URL, audit |
| `[DBSEC] Design audit log schema` | `type:security`, `area:database`, `priority:critical` | Critical | Actor/action/resource/result/request ID |
| `[DBSEC] Define retention delete and anonymize policy` | `type:security`, `area:database`, `priority:critical`, `risk:biometric` | Critical | Retention matrix, dry-run, approval |
| `[DBSEC] Define encrypted backup and restore drill` | `type:ops`, `area:devops`, `area:database`, `priority:critical`, `risk:production` | Critical | Backup mã hóa, restore test |
| `[DBSEC] Define database hardening checklist` | `type:security`, `area:database`, `priority:high`, `risk:production` | High | Network, account, TLS, least privilege |
| `[DBSEC] Define database encryption test matrix` | `type:qa`, `area:qa`, `area:database`, `priority:high` | High | Migration/encryption/auth/retention/backup |
| `[DBSEC] Sync DBSEC issues with GitHub project` | `type:ops`, `area:devops`, `priority:medium` | Medium | Labels/milestones/project board |

## M4 - AI/ANSVIS Integration

| Title | Labels | Priority | Notes |
|---|---|---|---|
| `[AI] Define ANSVIS HTTP Trigger payload contract` | `type:ai`, `area:ansvis`, `priority:critical` | Critical | Payload tối thiểu, normalized event, mock/sanitized fixture |
| `[AI] Define 34-camera task mapping matrix` | `type:ai`, `area:ansvis`, `priority:critical`, `risk:production` | Critical | Mapping camera, khu vực, task, ROI, threshold |
| `[AI] Configure Facial Recognition for attendance and timekeeping` | `type:ai`, `area:ansvis`, `priority:critical`, `risk:biometric` | Critical | Face Detection/Facial Recognition dùng chung cho học sinh và giáo viên |
| `[AI] Design Littering Detection custom pipeline` | `type:ai`, `area:ai-model`, `priority:high`, `risk:customer-impact` | High | Person/object tracking, vùng bỏ rác, vật bị bỏ lại |
| `[AI] Design Smoking Detection custom pipeline` | `type:ai`, `area:ai-model`, `priority:high`, `risk:customer-impact` | High | Nghi vấn hút thuốc, human review |
| `[AI] Design Student Uniform Detection custom pipeline` | `type:ai`, `area:ai-model`, `priority:high`, `risk:customer-impact` | High | Uniform correct/incorrect, thẻ học sinh, logo/màu nếu có |
| `[AI] Design Kitchen PPE Detection custom pipeline` | `type:ai`, `area:ai-model`, `priority:high`, `risk:customer-impact` | High | Mũ, khẩu trang, tạp dề, găng tay, đồng phục, giày bảo hộ |
| `[AI] Define happiness index scope and privacy guardrails` | `type:ai`, `area:ai-model`, `risk:customer-impact`, `risk:biometric` | Optional/Future | Không thuộc baseline sáu chức năng; chỉ mở lại bằng change request riêng |
| `[AI] Define per-pipeline AI acceptance metrics` | `type:ai`, `area:ai-model`, `priority:high`, `risk:customer-impact` | High | Baseline, shadow, training-needed, production-ready |
| `[AI] Build ANSVIS Adapter skeleton` | `type:ai`, `area:ansvis`, `priority:high` | High | Validate/normalize; raw ANSVIS không lan vào business/Web/Mobile |
| `[SEC] Add ANSVIS webhook auth and source validation` | `type:security`, `area:ansvis`, `priority:critical` | Critical | Token/HMAC/source |
| `[AI] Add event idempotency rules` | `type:ai`, `area:backend`, `priority:critical` | Critical | Chống ghi trùng |
| `[AI] Add sanitized ANSVIS payload contract tests` | `type:qa`, `area:ansvis`, `priority:high` | High | Không dùng payload thật |
| `[AI] Define AI shadow mode and human review rules` | `type:ai`, `area:ai-model`, `priority:high`, `risk:customer-impact` | High | Bắt buộc trước production; train/fine-tune chỉ khi baseline không đạt |

## M3/M4 - Backend business modules

| Title | Labels | Priority | Notes |
|---|---|---|---|
| `[BE] Define OpenAPI and error response standard` | `type:docs`, `area:backend`, `priority:critical` | Critical | API contract trước khi Web/Mobile tích hợp |
| `[BE] Build Camera Registry Service` | `type:feature`, `area:backend`, `priority:high` | High | Camera metadata, zone, ANSVIS mapping |
| `[BE] Build Event Ingestion Service` | `type:feature`, `area:backend`, `priority:critical`, `risk:production` | Critical | Validate event, queue/outbox, metadata |
| `[BE] Build Attendance Service` | `type:feature`, `area:backend`, `priority:critical`, `risk:biometric` | Critical | Điểm danh học sinh, đi trễ, review |
| `[BE] Build Timekeeping Service` | `type:feature`, `area:backend`, `priority:high` | High | Chấm công giáo viên/cán bộ |
| `[BE] Build Violation Service` | `type:feature`, `area:backend`, `priority:high`, `risk:customer-impact` | High | Vi phạm, review, correction |
| `[BE] Build Notification Service` | `type:feature`, `area:backend`, `priority:high`, `risk:data-leak` | High | In-app/push/email policy |
| `[BE] Build Report and Export Service` | `type:feature`, `area:backend`, `priority:high`, `risk:data-leak` | High | Dashboard/export có audit |
| `[BE] Build Evidence Storage Service` | `type:feature`, `area:backend`, `area:database`, `priority:critical`, `risk:data-leak` | Critical | Metadata, signed URL, retention |
| `[BE] Build AI Model Registry Service` | `type:feature`, `area:backend`, `area:ai-model`, `priority:high` | High | Model version, metric, approval |
| `[BE] Build Retention and Data Lifecycle Job` | `type:security`, `area:database`, `priority:critical`, `risk:biometric` | Critical | Xóa/ẩn danh theo policy |

## M5 - Web / Mobile / QA / Operations

| Title | Labels | Priority | Notes |
|---|---|---|---|
| `[WEB] Create Web Portal skeleton` | `type:feature`, `area:web`, `priority:high` | High | Next.js |
| `[WEB] Build login MFA and session timeout UI` | `type:feature`, `area:web`, `priority:high`, `risk:permission` | High | Auth UI |
| `[WEB] Build BGH dashboard` | `type:feature`, `area:web`, `priority:high` | High | Attendance, violation, camera overview |
| `[WEB] Build attendance view` | `type:feature`, `area:web`, `priority:high`, `risk:permission` | High | Theo lớp/ngày/quyền |
| `[WEB] Build parent portal view` | `type:feature`, `area:web`, `priority:high`, `risk:permission` | High | Vì yêu cầu có Web Portal cho phụ huynh |
| `[WEB] Build teacher class view` | `type:feature`, `area:web`, `priority:high`, `risk:permission` | High | Giáo viên xem lớp được phân công |
| `[WEB] Build violation review screen` | `type:feature`, `area:web`, `priority:high`, `risk:customer-impact` | High | Review/approve/reject |
| `[WEB] Build report and export screen` | `type:feature`, `area:web`, `priority:high`, `risk:data-leak` | High | Export có audit |
| `[WEB] Build user role admin screen` | `type:feature`, `area:web`, `priority:high`, `risk:permission` | High | User/role/permission |
| `[WEB] Build consent privacy screen` | `type:security`, `area:web`, `priority:critical`, `risk:biometric` | Critical | Consent/rút consent |
| `[WEB] Build camera ANSVIS status screen` | `type:feature`, `area:web`, `priority:medium` | Medium | Camera/task/event health |
| `[WEB] Harden Web Portal security` | `type:security`, `area:web`, `priority:critical`, `risk:permission` | Critical | Route guard, CSP, XSS/CSRF/IDOR |
| `[MOB] Create React Native app skeleton` | `type:feature`, `area:mobile`, `priority:high` | High | React Native |
| `[MOB] Build mobile auth refresh and logout flow` | `type:feature`, `area:mobile`, `priority:high`, `risk:permission` | High | Login/logout/refresh |
| `[MOB] Implement secure token storage` | `type:security`, `area:mobile`, `priority:critical`, `risk:data-leak` | Critical | Keychain/Keystore |
| `[MOB] Build parent home screen` | `type:feature`, `area:mobile`, `priority:high` | High | Tổng quan thông tin con |
| `[MOB] Build child attendance screen` | `type:feature`, `area:mobile`, `priority:high`, `risk:permission` | High | Phụ huynh chỉ xem con mình |
| `[MOB] Build notification list and detail` | `type:feature`, `area:mobile`, `priority:high`, `risk:data-leak` | High | Không lộ dữ liệu nhạy cảm |
| `[MOB] Build event detail permission guard` | `type:security`, `area:mobile`, `priority:critical`, `risk:permission` | Critical | Evidence theo quyền |
| `[MOB] Build consent flow` | `type:security`, `area:mobile`, `priority:critical`, `risk:biometric` | Critical | Đồng ý/rút consent |
| `[MOB] Build push token lifecycle` | `type:feature`, `area:mobile`, `priority:high` | High | Register/revoke device token |
| `[MOB] Harden production mobile build` | `type:security`, `area:mobile`, `priority:critical`, `risk:data-leak` | Critical | Tắt debug logs, kiểm production build |
| `[SEC] Add Web/Mobile route guard rules` | `type:security`, `area:security`, `priority:critical`, `risk:permission` | Critical | Không lộ dữ liệu |
| `[QA] Define E2E test flow for attendance and violation` | `type:qa`, `area:qa`, `priority:high` | High | UAT chính |
| `[QA] Define 34-camera performance benchmark plan` | `type:qa`, `area:qa`, `priority:high`, `risk:production` | High | Event ingestion, queue, storage, ANSVIS load |
| `[QA] Define UAT acceptance matrix` | `type:qa`, `area:qa`, `priority:critical`, `risk:customer-impact` | Critical | Nghiệm thu theo module |
| `[QA] Define production readiness gate checklist` | `type:qa`, `area:qa`, `priority:critical`, `risk:production` | Critical | Không code/go-live khi thiếu gate |
| `[OPS] Define backup and restore runbook` | `type:ops`, `area:devops`, `priority:critical`, `risk:production` | Critical | Trước go-live |
| `[OPS] Define deployment architecture and capacity baseline` | `type:ops`, `area:devops`, `priority:high`, `risk:production` | High | Server, network, DB, storage, GPU/ANSVIS assumptions |
| `[SEC] Define incident response runbook` | `type:security`, `area:security`, `priority:critical`, `risk:data-leak` | Critical | Rò rỉ dữ liệu |
| `[DOCS] Maintain requirements-to-issues traceability matrix` | `type:docs`, `area:docs`, `priority:high` | High | Đối chiếu yêu cầu khách hàng, plan và GitHub issues |

## GitHub CLI create command mẫu

Chỉ chạy sau khi đã đăng nhập GitHub CLI và có quyền repo:

```powershell
gh issue create --repo HIepNgoc2006/Camera-AI --title "[OPS] Configure GitHub Project board for boss tracking" --body "Create GitHub Project fields/views based on github-workflow/project-board-rules.md" --label "type:ops,area:devops,priority:high"
```
