# Pre-code readiness audit

## Kết luận ngắn

Trạng thái kiểm tra lại ngày 2026-07-13: **đủ điều kiện làm repository/codebase foundation an toàn, chưa đủ Definition of Ready để bắt đầu business module hoặc xử lý dữ liệu sinh trắc học.**

Bộ tài liệu có nền tảng tốt cho hệ thống trường học nhạy cảm dữ liệu, nhưng trạng thái thực thi chưa khớp với chất lượng planning: workspace local chưa là Git working tree, remote `main` gần như trống, phần lớn issue chưa có dependency/Definition of Done/evidence và các contract đầu vào vẫn đang mở.

## Evidence kiểm tra lại 2026-07-13

- Workspace `D:\WORKSAPCE\Camera AI` chưa phải Git working tree.
- Remote private `HIepNgoc2006/Camera-AI`, nhánh `main`, mới chỉ có README tối thiểu tại thời điểm kiểm tra.
- GitHub có 102 open issues; 95 issue thiếu dependency và 92/98 issue Critical/High thiếu dependency.
- 102/102 issue có milestone, prefix, type/area label và acceptance; 102/102 chưa có mục Definition of Done theo template hiện hành.
- Role/permission matrix, OpenAPI baseline, normalized ANSVIS event schema và mock/sanitized fixture chưa có artifact hoàn chỉnh trong workspace.
- Root `.gitignore` và `.env.example` an toàn đã được bổ sung local; chưa commit/push.

## Kết quả kiểm tra

| Hạng mục | Trạng thái | Nhận xét |
|---|---|---|
| Planning index | Đạt | Có đường dẫn đến master plan, security, AI, DB/encryption, QA, tracking, risk |
| Customer/project docs | Đạt | Có yêu cầu, business flow, architecture/API, UI, AI/security, test/risk, runbook |
| Agent rules | Đạt | Có rule security, database, AI/ANSVIS, logging, testing, verification |
| Database/encryption | Đạt sau bổ sung | Có file riêng cho PostgreSQL, encryption, key management, retention, backup, hardening |
| GitHub workflow | Đạt | Có labels, milestones, issue template, board rules, commit/push rules |
| GitHub issues | Chưa đạt execution readiness | Coverage đủ rộng nhưng dependency, DoD, evidence, test và priority cần chuẩn hóa trước khi triển khai tuần tự |
| Security coverage | Đạt | Có RBAC/ABAC, consent, audit, secret, DDoS, webhook hardening, log masking, backup |
| QA/UAT coverage | Đạt cơ bản | Có E2E, DDoS/abuse test, UAT acceptance matrix, production readiness gate |
| Operations coverage | Đạt cơ bản | Có backup/restore, monitoring, queue/DLQ, incident response, staging-production parity |
| Code readiness | Chỉ cho foundation | Cho phép làm repo safety, scaffold, CI và secret scan; chưa cho phép business/biometric implementation |

## GitHub issue coverage

Hiện GitHub repo có **102 open issues**:

| Nhóm | Số issue | Mục đích |
|---|---:|---|
| Foundation ban đầu | 28 | Docs, GitHub workflow, codebase foundation, backend/AI/Web/Mobile skeleton, QA/runbook |
| Risk/operations/security bổ sung | 18 | DDoS, NTP, ANSVIS capacity, signed URL, consent withdrawal, queue, backup, model drift |
| DBSEC | 12 | PostgreSQL, ERD, data classification, encryption, key rotation, audit, retention, hardening |
| Module chi tiết | 31 | Backend business services, Web/Mobile screens, UAT, production readiness |
| Traceability control | 8 | Các issue kiểm soát mapping, phạm vi optional, metric, Web view, benchmark và capacity; không phải chức năng mới |
| AI pipeline refinement | 5 | Facial Recognition dùng chung, Littering, Smoking, Student Uniform, Kitchen PPE |

## Những gì đã được bổ sung trong đợt audit

- Sửa issue template để không còn acceptance criteria trống.
- Thêm prefix `[DBSEC]` vào quy ước đặt tên issue.
- Bổ sung DBSEC vào GitHub backlog.
- Tạo script `github-workflow/create-dbsec-issues.ps1`.
- Tạo 12 GitHub issues DBSEC: #47-#58.
- Bổ sung backend/Web/Mobile/QA module issues vào GitHub backlog.
- Tạo script `github-workflow/create-module-issues.ps1`.
- Tạo 31 GitHub issues module: #59-#89.
- Cập nhật backlog tổng từ 58 lên 89 issues, sau đó lên 97 issues khi bổ sung traceability gap.
- Cập nhật GitHub lên 102 issues khi bổ sung hướng AI mới: Facial Recognition dùng chung và 4 custom pipelines.

## Các điểm cần review trước khi code

Trước khi bắt đầu scaffold/code, nên review theo thứ tự:

1. **Critical issues review**
   - Xem toàn bộ issue `priority:critical`.
   - Đảm bảo không có issue Critical thiếu acceptance criteria.

2. **Security gate review**
   - Consent.
   - RBAC/ABAC/object-level authorization.
   - Secret management.
   - Database encryption.
   - Audit log.
   - Evidence signed URL.
   - Backup/restore.

3. **Architecture review**
   - Microservices-ready monorepo.
   - PostgreSQL schema ownership.
   - API Gateway.
   - ANSVIS Adapter.
   - Outbox/idempotency.

4. **Implementation order review**
   - Vì chỉ có một developer, issue phải chạy tuần tự.
   - Không mở quá nhiều việc song song.
   - Mỗi issue trước khi làm phải có dependency rõ.
   - Chỉ issue có scope nhỏ, test/verification và evidence rõ mới được chuyển sang `Ready`.

5. **Go/no-go before coding**
   - Sáu chức năng baseline đã được khóa; happiness index ở Optional/Future Scope.
   - Issue Critical/High có dependency hoặc `Blocked by` rõ.
   - #90 khóa mapping 34 camera/task/model/ROI/event, bao gồm vị trí dùng Student Uniform.
   - #99-#102 có checklist baseline → shadow → train nếu cần → acceptance → rollback.
   - Dùng GitHub Project view Critical/High/Blocked để theo dõi; WIP triển khai chính bằng 1 vì chỉ có một developer.
   - Phân biệt repository/codebase foundation với business feature code: foundation an toàn được làm trước; business feature phải chờ đủ Definition of Ready.

## Rủi ro còn lại

| Rủi ro | Mức | Cách xử lý |
|---|---:|---|
| Issue nhiều, sếp nhìn bị rối | Trung bình | Dùng Executive Overview chỉ hiện Critical/High/Blocked |
| Một developer làm toàn bộ nên dễ quá tải | Cao | Giới hạn WIP, làm tuần tự theo milestone, luôn cập nhật evidence |
| Một số issue vẫn là plan/build cấp module | Trung bình | Dùng checklist trong issue; chỉ tách sub-issue khi công việc thực sự vượt 1-3 ngày hoặc cần evidence độc lập |
| Chưa có Project board thật được xác minh | Trung bình | Issue #4 và #58 cần kiểm tra khi setup board |
| Chưa có timeline chính thức | Thấp/Trung bình | User đã xác nhận thời gian đàm phán sau; vẫn cần thứ tự ưu tiên rõ |
| Workspace local chưa đồng bộ với remote | Rất cao | Không dùng `git add .`; review ignore/secret/media, tạo working tree đúng và đưa docs lên branch/PR có kiểm soát |
| Priority bị dàn đều Critical/High | Cao | Giữ Critical cho blocker/security gate thật; dùng risk label cho mức ảnh hưởng |

## Kết luận

Planning đủ làm baseline quản lý dự án. Có thể tiếp tục codebase foundation an toàn; chưa chuyển sang business module cho tới khi dependency Critical/High, role/permission matrix, API/event contract, mapping #90 và checklist #99-#102 đạt các điều kiện go/no-go nêu trên.
