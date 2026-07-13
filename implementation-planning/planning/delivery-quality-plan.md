# Delivery, QA and acceptance plan

## Phase check

Mỗi phase phải có checklist trước khi đi tiếp.

| Phase | Check bắt buộc |
|---|---|
| Foundation | SRS, use case, data class, threat model, architecture baseline |
| Codebase | Repo structure, Docker Compose, `.env.example`, lint/test scaffold, secret scan |
| Backend | Auth, permission, audit, migration, OpenAPI |
| ANSVIS/AI | Mock payload, HTTP Trigger contract, idempotency, log masking |
| Web/Mobile | Route guard, API client, permission UI, error handling |
| Integration | E2E flow, queue retry, notification, report |
| Security | OWASP checklist, dependency/container scan, ZAP baseline |
| UAT | Test case, biên bản, known issue, training material |

## Test strategy

| Loại test | Mục tiêu |
|---|---|
| Unit test | Business rule, policy, parser, validation |
| Integration test | API + DB + queue + storage |
| Contract test | ANSVIS payload, OpenAPI, mobile/web client |
| E2E test | Login, điểm danh, vi phạm, notification, report |
| Security test | RBAC/ABAC, object-level auth, injection, XSS, secret scan |
| Performance test | Event ingestion, queue backlog, report query |
| UAT | Nhà trường xác nhận flow nghiệp vụ |

## Acceptance criteria chính

| Module | Tiêu chí nghiệm thu |
|---|---|
| Auth | Login/logout, MFA admin, phân quyền đúng |
| School profile | Quản lý học sinh/phụ huynh/giáo viên/lớp |
| Consent | Có trạng thái đồng ý, chặn biometric nếu thiếu consent |
| Camera registry | Quản lý metadata camera, không lộ credential |
| ANSVIS integration | Nhận event, validate, idempotency, không log ảnh/base64 |
| Attendance | Ghi nhận điểm danh, xem theo quyền, đối soát |
| Timekeeping | Chấm công cán bộ/giáo viên, báo cáo |
| Violation | Ghi nhận vi phạm, human review, evidence link |
| Notification | Gửi đúng người, không gửi ảnh nhạy cảm |
| Report | Dashboard và export có audit |
| Security | Scan không còn Critical/High chưa xử lý |
| Operations | Backup/restore, monitoring, rollback |

## Bug severity

| Mức | Định nghĩa | SLA nội bộ đề xuất |
|---|---|---|
| Critical | Rò rỉ dữ liệu, sai phân quyền, hệ thống không dùng được | Xử lý ngay |
| High | Lỗi nghiệp vụ chính, mất event, notification sai người | Ưu tiên cao |
| Medium | Lỗi flow phụ, UI sai, report thiếu | Xử lý theo sprint |
| Low | Cosmetic, wording, cải tiến nhỏ | Gom xử lý định kỳ |

## Release checklist

- Migration đã chạy staging.
- Test pass theo scope.
- Secret scan pass.
- Dependency/container scan pass.
- `.env.example` cập nhật.
- Backup trước release.
- Rollback plan rõ.
- Release note có thay đổi, rủi ro, cách kiểm tra.\n