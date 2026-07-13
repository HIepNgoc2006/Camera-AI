# KẾ HOẠCH BACKLOG/TASK TRIỂN KHAI CHI TIẾT HỆ THỐNG AI CAMERA

## 0. Tóm tắt điều hành

Hệ thống AI Camera trường học là hệ thống phần mềm có mức nhạy cảm cao vì xử lý dữ liệu trẻ em, khuôn mặt, điểm danh, chấm công, ảnh/video sự kiện và dữ liệu vi phạm. Vì vậy backlog triển khai không chỉ liệt kê tính năng, mà phải bao gồm đầy đủ task về bảo mật, kiểm thử, vận hành, backup/restore, quản lý AI model và phản ứng sự cố.

Repo GitHub hiện đã có **97 issue mở** gồm:

- 28 issue khởi động cho tài liệu, GitHub workflow, nền codebase, backend core, AI/ANSVIS, Web/Mobile skeleton, QA và runbook.
- 18 issue bổ sung cho các rủi ro hệ thống như DDoS/API abuse, NTP/time sync, ANSVIS license/GPU capacity, signed URL, notification privacy, consent withdrawal, backup restore drill, queue backpressure, model drift, staging-production parity và fixture safety.
- 12 issue DBSEC bổ sung cho PostgreSQL, ERD, data classification, application-level encryption, key management, object storage evidence, audit log, retention, backup encryption, database hardening và test matrix.
- 31 issue module chi tiết bổ sung cho OpenAPI, backend business services, Web Portal screens, Mobile App screens, UAT acceptance matrix và production readiness gate.
- 8 issue traceability gap bổ sung cho 34-camera mapping, happiness index, per-violation metrics, parent/teacher Web Portal, 34-camera benchmark, deployment/capacity baseline và requirements-to-issues matrix.

Bộ backlog hiện tại đủ để bắt đầu quản lý dự án trên GitHub. Phần kế hoạch bên dưới mô tả backlog chi tiết theo module để triển khai đầy đủ hệ thống từ foundation đến go-live.

## 1. Mục tiêu

Tài liệu này chuyển kế hoạch phát triển hệ thống AI Camera trường học thành backlog/task có thể theo dõi trên GitHub Issues.

Mục tiêu:

- Biến kế hoạch tổng thể thành đầu việc rõ ràng.
- Không bỏ sót backend, AI/ANSVIS, Web, Mobile, security, test, operations.
- Mỗi nhóm task có đầu ra cụ thể.
- Mỗi phase có kiểm tra chất lượng và bảo mật.
- Tạo nền để theo dõi tiến độ, bug, rủi ro, security gate, test evidence và nghiệm thu.

Tài liệu này không thay đổi phạm vi phần mềm đã thống nhất. Nó chỉ chia nhỏ kế hoạch thành các đầu việc có thể triển khai, kiểm tra và bàn giao.

## 1.1 Phạm vi áp dụng

| Trong phạm vi | Ngoài phạm vi |
|---|---|
| Backend/API | Mua camera |
| AI/ANSVIS integration | Lắp đặt camera |
| Web Portal | Đi dây mạng vật lý |
| Mobile App React Native | Thi công hạ tầng điện/mạng |
| Database, queue, object storage | Bảo trì phần cứng camera |
| Security, audit, privacy, consent | Khảo sát hiện trường nếu không có phụ lục riêng |
| Monitoring, backup, deployment, runbook | Trực vận hành 24/7 nếu chưa có SLA riêng |

## 2. Nguyên tắc triển khai backlog

| Nguyên tắc | Cách áp dụng |
|---|---|
| Làm tuần tự | Dự án hiện do một developer chính triển khai, không giả định nhiều người làm song song |
| Security-first | Mỗi phase có security task/check riêng |
| Test đi kèm implementation | Task kỹ thuật phải có test hoặc bằng chứng kiểm tra |
| Issue không quá lớn | Mỗi issue có đầu ra rõ và review được |
| Không đưa phần cứng vào scope | Không tạo task khảo sát/lắp camera/đi dây |
| Không đưa dữ liệu thật lên GitHub | Không đưa `.env`, secret, ảnh mặt, video camera, face DB, dữ liệu học sinh thật vào issue |
| Có Definition of Done | Mỗi task có tiêu chí hoàn thành rõ |

## 3. Milestone triển khai

| Milestone | Nội dung |
|---|---|
| M1 - Docs Baseline | Tài liệu, planning, GitHub workflow |
| M2 - Codebase Foundation | Monorepo, Docker, CI, `.env.example`, secret scan |
| M3 - Backend Core | Auth, user, school, consent, audit, database |
| M4 - AI/ANSVIS Integration | Webhook, event ingestion, AI pipeline, shadow mode |
| M5 - Web Portal | Dashboard, admin, report, review, consent |
| M6 - Mobile App | React Native app, parent/teacher/BGH flow |
| M7 - Integration & QA | E2E, contract test, security test, performance |
| M8 - Security Hardening | Scan, backup/restore, incident response, go-live gate |
| M9 - UAT & Go-live | Bàn giao, đào tạo, vận hành, hyper-care |

## 4. Backlog hiện tại đã có trên GitHub

Hiện đã có **97 issue mở** trên GitHub.

Nhóm 28 issue khởi động:

- Review tài liệu compact.
- Review implementation planning.
- Review AGENTS rules.
- Cấu hình GitHub Project board.
- Tạo labels/milestones.
- Khởi tạo monorepo.
- `.gitignore` và `.env.example`.
- Docker Compose local stack.
- Secret scanning.
- Lint/test baseline.
- API Gateway skeleton.
- Identity Service skeleton.
- RBAC/object-level authorization.
- School Service schema.
- Consent Service baseline.
- Audit log baseline.
- ANSVIS HTTP Trigger contract.
- ANSVIS Adapter skeleton.
- ANSVIS webhook auth/source validation.
- Event idempotency.
- Sanitized ANSVIS contract tests.
- AI shadow mode/human review.
- Web Portal skeleton.
- React Native skeleton.
- Web/Mobile route guard.
- E2E attendance/violation flow.
- Backup/restore runbook.
- Incident response runbook.

Nhóm 18 issue rủi ro/vận hành bổ sung:

- NTP/timezone synchronization.
- ANSVIS license, task limit và GPU capacity.
- Signed URL TTL và evidence access audit.
- Notification privacy policy.
- Consent withdrawal và data deletion workflow.
- Backup restore drill.
- Queue backpressure và DLQ alert.
- Lost-device/session revoke flow.
- Model drift monitoring.
- Report/export load test.
- Environment misconfiguration checklist.
- Data fixture/seed safety check.
- Staging-production parity checklist.
- ANSVIS backup limitation checklist.
- AI appeal/manual correction workflow test.
- DDoS threat model/protection strategy.
- ANSVIS webhook flood/replay/large payload hardening.
- DDoS/API abuse traffic test plan.

Nhóm 12 issue database security/encryption bổ sung:

- Complete database and encryption plan.
- Design ERD and data dictionary.
- Classify data by table and field.
- Define application-level encryption rules.
- Define key management and rotation plan.
- Define object storage evidence policy.
- Design audit log schema.
- Define retention delete and anonymize policy.
- Define encrypted backup and restore drill.
- Define database hardening checklist.
- Define database encryption test matrix.
- Sync DBSEC issues with GitHub project.

Nhóm 31 issue module chi tiết bổ sung:

- OpenAPI and error response standard.
- Camera Registry Service.
- Event Ingestion Service.
- Attendance Service.
- Timekeeping Service.
- Violation Service.
- Notification Service.
- Report and Export Service.
- Evidence Storage Service.
- AI Model Registry Service.
- Retention and Data Lifecycle Job.
- Web login/MFA/session timeout.
- Web BGH dashboard.
- Web attendance view.
- Web violation review.
- Web report/export.
- Web user/role admin.
- Web consent/privacy.
- Web camera/ANSVIS status.
- Web security hardening.
- Mobile auth/refresh/logout.
- Mobile secure token storage.
- Mobile parent home.
- Mobile child attendance.
- Mobile notification list/detail.
- Mobile event detail permission guard.
- Mobile consent flow.
- Mobile push token lifecycle.
- Mobile production hardening.
- UAT acceptance matrix.
- Production readiness gate checklist.

Nhóm 8 issue traceability gap bổ sung:

- 34-camera task mapping matrix.
- Happiness index scope and privacy guardrails.
- Per-violation AI acceptance metrics.
- Parent Web Portal view.
- Teacher class Web view.
- 34-camera performance benchmark plan.
- Deployment architecture and capacity baseline.
- Requirements-to-issues traceability matrix.

Các issue này là nền quản lý và kiểm soát rủi ro. Các phần tiếp theo là backlog module chi tiết để triển khai đầy đủ.

## 5. Backlog chi tiết

Tổng số task chi tiết trong phần này: **92 task**.

| Nhóm | Số task |
|---|---:|
| Foundation, GitHub và DevOps | 8 |
| Backend và database | 15 |
| Database security và encryption | 12 |
| Security và privacy | 16 |
| AI/ANSVIS và dữ liệu AI | 15 |
| Web Portal | 9 |
| Mobile App | 10 |
| QA, UAT và performance | 13 |

### 5.1 Foundation, GitHub và DevOps

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| OPS-01 | Push tài liệu hiện tại lên repo GitHub | Scan secret, kiểm file nhạy cảm, commit/push tài liệu đã chuẩn hóa | Repo có tài liệu nền | Cao | GitHub workflow |
| OPS-02 | Thiết lập branch protection | Chặn push trực tiếp vào main khi bắt đầu code chính thức | Branch protection rule | Cao | OPS-01 |
| OPS-03 | Thiết lập GitHub Project board | Tạo views Executive, Security, Bug, AI, UAT | Project board theo dõi tiến độ | Cao | Labels/milestones |
| OPS-04 | Thiết lập GitHub Actions CI baseline | Chạy lint/test/secret scan cơ bản | CI workflow | Cao | Monorepo skeleton |
| OPS-05 | Thiết lập pre-commit hooks | Format, lint, secret scan trước commit | Pre-commit config | Trung bình | CI baseline |
| OPS-06 | Thiết lập environment matrix | Local/staging/production config policy | Environment matrix | Cao | `.env.example` |
| OPS-07 | Thiết lập reverse proxy/TLS plan | Nginx/Traefik, domain, HTTPS, routing | TLS/reverse proxy plan | Cao | API Gateway |
| OPS-08 | Thiết lập release/rollback checklist | Checklist trước deploy và cách quay lại | Release runbook | Cao | CI baseline |

### 5.2 Backend và database

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| BE-01 | Camera Registry Service | Quản lý camera metadata, khu vực, mapping ANSVIS | Camera registry API/schema | Cao | School schema |
| BE-02 | Event Ingestion Service | Nhận event, validate, lưu metadata, đưa queue | Event ingestion service | Rất cao | ANSVIS Adapter |
| BE-03 | Attendance Service | Xử lý điểm danh học sinh, đi trễ, đối soát | Attendance API/service | Rất cao | Event Ingestion |
| BE-04 | Timekeeping Service | Chấm công cán bộ/giáo viên | Timekeeping API/service | Cao | Event Ingestion |
| BE-05 | Violation Service | Quản lý vi phạm, trạng thái review, evidence | Violation workflow | Cao | Event Ingestion |
| BE-06 | Notification Service | In-app/push/email policy, device token, delivery log | Notification service | Cao | Attendance/Violation |
| BE-07 | Report Service | Dashboard, thống kê, export có audit | Report service | Cao | Attendance/Violation |
| BE-08 | Evidence Storage Service | Metadata ảnh/video, signed URL, retention | Evidence storage API | Rất cao | Object storage |
| BE-09 | AI Model Registry Service | Model version, metric, dataset hash, approval | AI model registry | Cao | AI plan |
| BE-10 | Retention/Data Lifecycle Job | Xóa/ẩn danh dữ liệu theo policy | Retention jobs | Rất cao | Data classification |
| DB-01 | PostgreSQL schemas by domain | Tạo schema identity/school/privacy/camera/events/... | Migration nền | Rất cao | Monorepo |
| DB-02 | Migration workflow | Alembic/migration rule/rollback guideline | Migration workflow | Cao | DB-01 |
| DB-03 | Event idempotency table | Unique key, replay protection, duplicate handling | Idempotency table | Rất cao | Event Ingestion |
| DB-04 | Audit tables/indexes | Append-only audit, index truy vấn | Audit schema | Rất cao | Audit baseline |
| DB-05 | Report read-model strategy | Materialized view/read model cho dashboard | Reporting model | Trung bình | Report Service |

### 5.2.1 Database security và encryption

Nhóm task này bổ sung lớp bảo vệ dữ liệu cho PostgreSQL, object storage, backup và dữ liệu sinh trắc học. Đây là điều kiện bắt buộc trước khi dùng dữ liệu thật hoặc go-live.

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| DBSEC-01 | Hoàn thiện database and encryption plan | Chuẩn hóa PostgreSQL schema, mã hóa, key management, backup, retention | `database-and-encryption-plan.md` | Rất cao | Docs baseline |
| DBSEC-02 | Thiết kế ERD và data dictionary | Liệt kê bảng, field, khóa, quan hệ, index, owner domain | ERD + data dictionary | Rất cao | DBSEC-01 |
| DBSEC-03 | Phân loại dữ liệu theo bảng/field | Xác định PII, biometric, evidence, event, secret metadata | Field-level data classification | Rất cao | DBSEC-02 |
| DBSEC-04 | Thiết kế application-level encryption | Chọn field cần mã hóa, `key_id`, HMAC/hash lookup nếu cần search | Encryption design | Rất cao | DBSEC-03 |
| DBSEC-05 | Thiết kế key management và rotation | Secret manager/KMS, rotate, revoke, recovery, audit | Key management runbook | Rất cao | DBSEC-04 |
| DBSEC-06 | Thiết kế object storage evidence policy | Metadata table, private bucket, signed URL TTL, access audit | Evidence storage policy | Rất cao | DBSEC-03 |
| DBSEC-07 | Thiết kế audit log schema | Audit event list, actor/resource/action/result/request ID | Audit schema | Rất cao | DBSEC-02 |
| DBSEC-08 | Thiết kế retention/delete/anonymize policy | Policy theo loại dữ liệu, dry-run, approval, audit | Retention matrix | Rất cao | DBSEC-03 |
| DBSEC-09 | Thiết kế backup encryption và restore drill | Backup mã hóa, restore test, RPO/RTO, quyền restore | Backup/restore checklist | Rất cao | DBSEC-05 |
| DBSEC-10 | Thiết kế database hardening checklist | Network, account, least privilege, TLS, backup, scan | DB hardening checklist | Cao | DBSEC-09 |
| DBSEC-11 | Viết test plan cho database/encryption | Migration, encryption, permission, consent, retention, backup test | DB/security test matrix | Cao | DBSEC-04 |
| DBSEC-12 | Tạo GitHub issues DBSEC | Đưa nhóm DBSEC lên GitHub Issues, label/milestone rõ | Issues DBSEC | Trung bình | DBSEC-01 |

### 5.3 Security và privacy

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| SEC-01 | Threat model toàn hệ thống | Xác định asset, threat, attack path, mitigation | Threat model | Rất cao | Architecture baseline |
| SEC-02 | Data classification & retention register | Phân loại dữ liệu và thời hạn lưu | Data inventory/register | Rất cao | Docs baseline |
| SEC-03 | Secret manager strategy | Chọn Infisical/Doppler/Vault/cloud secret manager | Secret management plan | Rất cao | Environment matrix |
| SEC-04 | Log masking policy and tests | Không log PII/biometric/token/base64 | Log masking test | Rất cao | Logging setup |
| SEC-05 | MFA Admin/BGH | MFA cho tài khoản quan trọng | MFA flow | Rất cao | Identity Service |
| SEC-06 | Permission matrix test suite | Test phụ huynh/GV/BGH/admin đúng quyền | Permission tests | Rất cao | RBAC |
| SEC-07 | Consent enforcement test suite | Test block biometric khi thiếu consent | Consent tests | Rất cao | Consent Service |
| SEC-08 | Dependency scan Python/JS | pip-audit/npm audit/pnpm audit | Dependency scan workflow | Cao | CI |
| SEC-09 | Container scan | Trivy scan image/config | Container scan report | Cao | Dockerfile |
| SEC-10 | OWASP ZAP baseline | Scan Web/API trước go-live | ZAP report | Cao | Staging |
| SEC-11 | Export audit/watermark policy | Audit export report/evidence | Export policy | Cao | Report/Evidence |
| SEC-12 | Incident notification decision tree | Khi nào thông báo nhà trường/phụ huynh | Incident decision tree | Rất cao | Incident runbook |
| SEC-13 | DDoS/rate limit protection strategy | WAF/CDN, API Gateway rate limit, endpoint quota | DDoS protection plan | Rất cao | API Gateway |
| SEC-14 | Notification privacy policy | Nội dung push tối giản, không lộ dữ liệu nhạy cảm | Notification privacy rule | Rất cao | Notification Service |
| SEC-15 | Signed URL and evidence access audit | TTL signed URL, audit view/export evidence | Evidence access policy | Rất cao | Evidence Storage |
| SEC-16 | Consent withdrawal and data deletion workflow | Rút consent, xóa/ẩn danh dữ liệu liên quan | Consent lifecycle workflow | Rất cao | Consent Service |

### 5.4 AI/ANSVIS và dữ liệu AI

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| AI-01 | Verify ANSVIS version/license/tasks | Kiểm version, license, max running tasks, GPU | Capability matrix | Rất cao | ANSVIS access |
| AI-02 | Camera-zone-task mapping | Ánh xạ camera, khu vực, task, model, ROI | Camera mapping matrix | Rất cao | Camera handover |
| AI-03 | ANSVIS task config versioning | Version hóa task, ROI, threshold, model | Task config registry | Cao | AI-02 |
| AI-04 | Event Storage/media retention policy | Quy định lưu Event Log, snapshot, video | Retention policy | Cao | Security plan |
| AI-05 | Face recognition consent/enrollment | Luồng enrollment có consent | Enrollment workflow | Rất cao | Consent Service |
| AI-06 | Dataset manifest template | Nguồn, consent, label, hash, retention | Dataset manifest | Rất cao | AI data plan |
| AI-07 | Model card template | Metric, limitation, dataset, reviewer | Model card | Cao | AI-06 |
| AI-08 | Model artifact/version/checksum | Lưu model có version/checksum | Model registry workflow | Cao | AI Model Registry |
| AI-09 | False-positive/false-negative review | Review event sai/bỏ sót | Review workflow | Cao | Violation Service |
| AI-10 | Model rollback workflow | Quay lại version model cũ | Model rollback runbook | Cao | AI-08 |
| AI-11 | ANSVIS Event Log export control | Quyền export, audit, dữ liệu được phép xuất | Export control policy | Rất cao | Security plan |
| AI-12 | Shadow mode report format | Báo cáo false alert, latency, confidence | Shadow mode report | Cao | Shadow mode issue |
| AI-13 | Model drift monitoring plan | Theo dõi false alert/missed detection sau go-live | Model drift dashboard/checklist | Cao | Shadow mode report |
| AI-14 | AI appeal/manual correction workflow | Quy trình phụ huynh/giáo viên phản hồi AI sai | Appeal/correction workflow | Cao | Violation Service |
| AI-15 | ANSVIS backup limitation checklist | Kiểm backup model/face DB/license/config | ANSVIS backup checklist | Cao | Backup runbook |

### 5.5 Web Portal

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| WEB-01 | Login/MFA/session timeout UI | Đăng nhập, MFA, timeout, logout | Auth UI | Cao | Identity API |
| WEB-02 | BGH dashboard | Tổng quan điểm danh, vi phạm, camera, cảnh báo | Dashboard | Cao | Report API |
| WEB-03 | Attendance view | Xem điểm danh theo lớp/ngày/quyền | Attendance UI | Cao | Attendance API |
| WEB-04 | Violation review screen | Review/approve/reject cảnh báo AI | Review UI | Cao | Violation API |
| WEB-05 | Report/export screen | Báo cáo và export có audit | Report UI | Cao | Report API |
| WEB-06 | User/role/admin screen | Quản lý user, role, phân quyền | Admin UI | Cao | Identity/School |
| WEB-07 | Consent/privacy screen | Quản lý consent và trạng thái dữ liệu | Consent UI | Rất cao | Consent API |
| WEB-08 | Camera/ANSVIS status screen | Theo dõi camera/task/event health | Ops UI | Trung bình | Camera Registry |
| WEB-09 | Web security hardening | Route guard, CSP, XSS/CSRF/IDOR checklist | Hardened Web | Rất cao | Web screens |

### 5.6 Mobile App

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| MOB-01 | Mobile login/logout/refresh | Login, refresh, revoke, logout | Auth flow | Cao | Mobile skeleton |
| MOB-02 | Secure token storage | Keychain/Keystore secure storage | Secure storage | Rất cao | MOB-01 |
| MOB-03 | Parent home screen | Tổng quan thông tin con | Parent home | Cao | School/Attendance API |
| MOB-04 | Child attendance screen | Điểm danh con theo ngày | Attendance mobile | Cao | Attendance API |
| MOB-05 | Notification list/detail | Danh sách và chi tiết thông báo | Notification UI | Cao | Notification API |
| MOB-06 | Event detail permission guard | Xem sự kiện/evidence theo quyền | Event detail UI | Rất cao | Evidence API |
| MOB-07 | Consent flow | Xem/đồng ý/rút consent theo chính sách | Consent mobile | Rất cao | Consent API |
| MOB-08 | Device token register/revoke | Push token lifecycle | Push setup | Cao | Notification Service |
| MOB-09 | Disable production debug logs | Tắt debug log, kiểm build production | Hardened mobile build | Rất cao | Mobile app |
| MOB-10 | Lost-device/session revoke flow | Revoke token, logout all devices, refresh token rotation | Lost-device response flow | Cao | Secure storage |

### 5.7 QA, UAT và performance

| ID | Task | Nội dung | Đầu ra | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|---|
| QA-01 | Unit test strategy per service | Business rule, policy, parser | Unit test plan | Cao | Service skeleton |
| QA-02 | Integration test strategy | API + DB + queue + storage | Integration test plan | Cao | Local stack |
| QA-03 | ANSVIS contract fixtures | Sanitized event payload fixtures | Contract fixtures | Rất cao | ANSVIS contract |
| QA-04 | Security test checklist | RBAC, consent, injection, XSS, secret scan | Security test checklist | Rất cao | Security plan |
| QA-05 | Performance test plan | Event ingestion, queue backlog, report query | Performance plan | Cao | Event ingestion |
| QA-06 | UAT test case pack | Test case cho nhà trường/BGH/GV/phụ huynh | UAT pack | Cao | Web/Mobile |
| QA-07 | Regression checklist | Checklist trước release candidate | Regression checklist | Cao | QA baseline |
| QA-08 | Production smoke test | Kiểm nhanh sau deploy production | Smoke test checklist | Cao | Deployment |
| QA-09 | Report/export load test | Kiểm query nặng, async export, rate limit | Export load test report | Cao | Report Service |
| QA-10 | Environment misconfiguration checklist | Kiểm không dùng nhầm secret/config giữa môi trường | Environment check report | Cao | Environment matrix |
| QA-11 | Data fixture and seed safety check | Đảm bảo fixture/seed không dùng dữ liệu thật | Fixture safety report | Rất cao | Test setup |
| QA-12 | Staging-production parity checklist | So sánh config/hạ tầng staging và production | Parity checklist | Cao | Staging |
| QA-13 | DDoS/abuse traffic test plan | Test rate limit, webhook flood, login throttling | Abuse test plan | Cao | API Gateway |

## 6. Security/Test gates theo phase

| Gate | Điều kiện phải đạt |
|---|---|
| Gate 1 - Trước coding | Có AGENTS rules, `.env.example`, `.gitignore`, secret scan baseline |
| Gate 2 - Backend core | Auth/RBAC/ABAC, consent, audit và migration có test |
| Gate 3 - AI/ANSVIS | Webhook auth, schema validation, idempotency, không log media/base64 |
| Gate 4 - Web/Mobile | Route guard, secure token storage, permission UI, không lộ dữ liệu |
| Gate 5 - Integration | E2E camera/event/web/mobile/notification pass bằng dữ liệu giả/sanitized |
| Gate 6 - Security hardening | Dependency scan, container scan, OWASP ZAP, không còn Critical/High chưa xử lý |
| Gate 7 - Go-live | Backup/restore, rollback, monitoring, incident runbook, UAT evidence |

Nếu gate chưa đạt, hệ thống chỉ nên ở trạng thái local, staging, demo, pilot hoặc shadow mode; không chuyển production chính thức.

## 7. Definition of Done chung cho mọi issue

Một issue chỉ được đóng khi có đủ:

- Output đúng mô tả task.
- Không chứa secret/dữ liệu thật.
- Test hoặc bằng chứng kiểm tra tương ứng.
- Security/privacy impact đã được xem xét.
- Docs/runbook được cập nhật nếu thay đổi hành vi.
- Nếu liên quan dữ liệu học sinh/sự kiện: có permission và audit check.
- Nếu liên quan AI/ANSVIS: có payload/schema/idempotency/log masking check.

## 8. Thứ tự triển khai đề xuất

| Thứ tự | Nhóm việc |
|---:|---|
| 1 | Hoàn thiện GitHub Project board, branch/commit/PR rules |
| 2 | Push tài liệu và thiết lập secret scan |
| 3 | Dựng monorepo + local Docker stack |
| 4 | Dựng backend foundation: API Gateway, Identity, School, Consent, Audit |
| 5 | Dựng Event Ingestion + ANSVIS Adapter |
| 6 | Dựng Attendance, Timekeeping, Violation |
| 7 | Dựng Notification, Report, Evidence Storage |
| 8 | Dựng AI governance: dataset, model registry, shadow mode |
| 9 | Dựng Web Portal |
| 10 | Dựng Mobile App |
| 11 | Chạy integration, security, performance, UAT |
| 12 | Hardening, runbook, go-live |

## 9. Rủi ro trọng yếu cần theo dõi xuyên suốt

| Rủi ro | Kiểm soát chính |
|---|---|
| DDoS/API abuse | WAF/CDN, rate limit, endpoint quota, alert |
| Webhook flood từ nguồn giả | IP allowlist, HMAC/token, body size limit, schema validation |
| Lệch giờ hệ thống | NTP/timezone policy cho camera/ANSVIS/backend/database |
| Signed URL bị chia sẻ | TTL ngắn, audit access, watermark/export policy |
| Mobile mất thiết bị | Secure storage, revoke token, logout all devices |
| Consent withdrawal chưa xử lý dữ liệu cũ | Data deletion/anonymize workflow |
| Model drift | Theo dõi false alert/missed detection, retrain plan |
| Staging khác production | Parity checklist |
| Backup ANSVIS thiếu face DB/model/license | Backup riêng và restore drill |
| Fixture/test seed dùng dữ liệu thật | Fixture safety check và fake data only |

## 10. Cách theo dõi trên GitHub

GitHub Issues/Projects được dùng làm nơi theo dõi chính.

| Thành phần | Cách dùng |
|---|---|
| Issue | Theo dõi từng task/bug/security risk |
| Label | Phân loại type, priority, area, risk |
| Milestone | Gom task theo phase M1-M9 |
| Project view | Cho dashboard tiến độ, blocker, security, bug, AI |
| Comment | Ghi bằng chứng test, log đã masking, quyết định kỹ thuật |
| Close issue | Chỉ đóng khi đạt Definition of Done |

View nên có:

- Executive Overview.
- Phase Board.
- Security & Risk.
- Bug Tracking.
- AI/ANSVIS Integration.
- UAT & Acceptance.
- Weekly Report.

## 11. Kết luận

Backlog hiện tại trên GitHub đã đủ để khởi động dự án, theo dõi phase lớn và kiểm soát các rủi ro trọng yếu ban đầu. Để triển khai đầy đủ hệ thống AI Camera cho trường học, cần tiếp tục chuyển backlog chi tiết trong tài liệu này thành issue theo từng đợt triển khai.

Việc bổ sung task không làm thay đổi phạm vi dự án; nó giúp các hạng mục đã có trong kế hoạch tổng thể trở thành các đầu việc rõ ràng, có thể theo dõi, kiểm thử, bảo mật và nghiệm thu.
