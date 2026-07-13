# System master plan

## Phạm vi

Hệ thống gồm phần mềm backend, AI integration, Web Portal, Mobile App, database, bảo mật, monitoring và vận hành. Phần khảo sát hiện trường, mua camera, lắp đặt camera, đi dây mạng vật lý không nằm trong phạm vi phần mềm.

Team phần mềm giả định chỉ có một developer chính, nên kế hoạch phải tuần tự, có checkpoint rõ ràng, không giả định nhiều người làm song song.

## Mục tiêu hệ thống

| Nhóm | Mục tiêu |
|---|---|
| Điểm danh | Nhận event từ camera/ANSVIS, xử lý điểm danh học sinh |
| Chấm công | Ghi nhận vào/ra của cán bộ, giáo viên |
| Vi phạm | Phát hiện đi trễ, đồng phục, xả rác, hút thuốc, thiếu bảo hộ bếp |
| Web Portal | Cho BGH/admin/giáo viên xem dashboard, quản lý, báo cáo |
| Mobile App | React Native cho phụ huynh/giáo viên/BGH theo quyền |
| AI/ANSVIS | Tích hợp ANSVIS/AIBOX, HTTP Trigger, Event Log, model/task |
| Security | Consent, RBAC/ABAC, audit, encryption, secret management |

## Hướng triển khai đã chốt

Kế hoạch chi tiết theo workstream nằm trong [workstream-implementation-plan.md](workstream-implementation-plan.md). Nguyên tắc điều phối:

- Backend, Web Portal, Mobile App, database và security được build như **Product Platform**, có thể chạy bằng mock/sanitized ANSVIS event và không phụ thuộc việc train AI.
- ANSVIS Integration là luồng riêng để nhận HTTP Trigger, validate, normalize, lưu event, theo dõi camera/task và hiển thị dashboard vận hành.
- AI custom pipeline/training là luồng riêng cho Littering, Smoking, Student Uniform và Kitchen PPE. Facial Recognition cho điểm danh/chấm công dùng model có sẵn của ANSVIS.
- Khi làm issue/code, không trộn việc train model vào issue Web/App/Backend nếu không có phụ thuộc trực tiếp.

## Phase triển khai compact

| Phase | Việc chính | Gate để qua phase |
|---|---|---|
| Foundation | Chốt SRS, use case, data classification, threat model, repo structure | Có tài liệu yêu cầu, data class, consent flow, architecture baseline |
| Codebase setup | Dựng monorepo, service skeleton, Docker Compose, env example, CI cơ bản | Secret scan chạy được, `.env.example` đủ, không có secret thật |
| Product Platform core | Auth, RBAC/ABAC, school profile, consent, audit, database migration | Test phân quyền, audit log, migration chạy được |
| ANSVIS Integration | Camera registry, ANSVIS adapter, event ingestion, payload mapping, camera/task health | Validate payload, idempotency, không log ảnh/base64, có mock/sanitized fixtures |
| Business modules | Attendance, timekeeping, violation, notification, report | Có business test, human review cho event nhạy cảm |
| Web/Mobile | Dashboard, quản trị, app phụ huynh/giáo viên/BGH | Route guard, permission test, không hiển thị sai dữ liệu |
| AI Pipeline | Facial Recognition integration; spec/test Littering, Smoking, Student Uniform, Kitchen PPE; train/fine-tune nếu cần | Shadow mode, metric, human review, rollback model/config |
| Integration & QA | E2E, staging, mock/pilot camera, performance baseline | Không còn lỗi Critical/High, E2E pass flow chính |
| Security hardening | OWASP review, scan, backup/restore, incident drill | Có scan report, backup restore evidence, rollback plan |
| UAT & Go-live | UAT với nhà trường, đào tạo, bàn giao, support | Biên bản nghiệm thu, tài khoản cá nhân, runbook vận hành |

## Work breakdown chính

| Nhóm việc | Task bắt buộc |
|---|---|
| PM/Docs | SRS, use case, business flow, event flow, acceptance criteria, risk register |
| Backend | API Gateway, auth, school profile, consent, camera registry, event ingestion, attendance, violation, notification, report |
| AI/ANSVIS | Đọc docs ANSCENTER/video tập huấn, cấu hình camera, Facial Recognition, HTTP Trigger, Event Log, Task Group, ROI/threshold, shadow mode; thiết kế Littering/Smoking/Student Uniform/Kitchen PPE pipeline và custom training nếu cần |
| Database | PostgreSQL schema, migration, audit table, event table, partition nếu cần, theo chi tiết trong `database-and-encryption-plan.md` |
| Web | BGH dashboard, giáo viên view, admin config, report/export, permission UI |
| Mobile | Login, home, attendance, notification, event detail, profile, secure token |
| Security | Threat model, RBAC/ABAC, MFA admin, secret manager, encryption, vulnerability scan, incident response |
| QA | Unit, integration, contract, E2E, UAT, security test, performance test |
| Ops | Docker, deploy staging/production, log, monitoring, backup, restore, release/rollback |

## Definition of Done cấp hệ thống

Một hạng mục chỉ được coi là xong khi có đủ:

- Code hoặc tài liệu đúng phạm vi.
- Test phù hợp với mức rủi ro.
- Permission và audit được kiểm tra nếu đụng dữ liệu nhạy cảm.
- Không log PII/biometric/secret.
- Có `.env.example` nếu thêm config.
- Có migration nếu thay đổi database.
- Có kiểm tra data classification, encryption, retention và audit theo `database-and-encryption-plan.md` nếu thay đổi database hoặc dữ liệu nhạy cảm.
- Có rollback hoặc cách disable nếu lỗi production.
- Có cập nhật docs/runbook nếu thay đổi vận hành.
