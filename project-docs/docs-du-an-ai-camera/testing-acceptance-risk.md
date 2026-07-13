# Testing, acceptance and risk

## Test plan

| Loại test | Mục tiêu |
|---|---|
| Unit test | Business rule, policy, parser, validation |
| Integration test | API + DB + queue + storage |
| Contract test | ANSVIS payload, OpenAPI, Web/Mobile client |
| E2E test | Login, điểm danh, vi phạm, notification, report |
| Security test | RBAC/ABAC, object-level auth, injection, XSS, secret scan |
| Performance test | Event ingestion, queue backlog, report query |
| UAT | Khách hàng xác nhận flow nghiệp vụ |

## Test case chính

| Module | Test case |
|---|---|
| Auth | Login/logout, MFA admin, token revoke, sai mật khẩu |
| Permission | Phụ huynh chỉ xem con mình, giáo viên chỉ xem lớp được phân công |
| Consent | Có consent thì xử lý, thiếu consent thì block biometric |
| ANSVIS webhook | Payload hợp lệ, payload sai, event trùng, source không hợp lệ |
| Attendance | Ghi nhận đúng ngày/giờ/lớp, xử lý đi trễ |
| Timekeeping | Ghi nhận vào/ra cán bộ/giáo viên |
| Violation | Tạo event, review, reject false positive |
| Notification | Gửi đúng người, không chứa ảnh nhạy cảm trong push |
| Report/export | Đúng dữ liệu, có audit khi export |
| Backup/restore | Backup tạo được, restore test được |

## Acceptance criteria

| Mốc | Tiêu chí nghiệm thu |
|---|---|
| Demo nghiệp vụ | Khách hàng xem được flow điểm danh/vi phạm/report bằng dữ liệu giả lập |
| Tích hợp ANSVIS | Backend nhận event từ ANSVIS, validate, chống trùng |
| UAT | Các vai trò dùng được flow chính theo quyền |
| Security review | Không còn lỗi Critical/High chưa xử lý; có audit và secret policy |
| Pilot | Chạy với một phần camera, đo event delay, false positive/false negative |
| Go-live | Có backup/restore, monitoring, rollback, tài khoản cá nhân, runbook |
| Nghiệm thu cuối | Khách hàng ký xác nhận module, dữ liệu, vận hành, support |

## Risk register

| Rủi ro | Mức | Phương án xử lý |
|---|---:|---|
| Lộ ảnh mặt/dữ liệu học sinh | Rất cao | Consent, encryption, audit, private storage, log masking |
| Phân quyền sai | Rất cao | RBAC/ABAC, object-level auth test |
| AI nhận diện sai | Cao | Threshold, shadow mode, human review |
| Event trùng/mất event | Cao | Idempotency, queue, retry, DLQ |
| ANSVIS task stop | Cao | Monitoring, alert, runbook |
| GPU/license không đủ cho 34 camera | Cao | Pilot benchmark, Active Engine, capacity review |
| Storage đầy | Cao | Retention, lifecycle, disk alert |
| Backup không đủ face DB/model | Cao | Backup riêng model/dataset/face DB nếu được phép |
| Notification sai người | Rất cao | Recipient test, permission check |
| Lệch giờ camera/ANSVIS/backend | Cao | NTP/timezone policy, timestamp test |
| DDoS hoặc abuse traffic | Cao | WAF/rate limit, webhook validation, monitoring |
| Signed URL bị chia sẻ | Cao | TTL ngắn, audit access, hạn chế export |
| Mobile mất thiết bị còn token | Cao | Secure storage, revoke token, logout all devices |
| Consent bị rút nhưng dữ liệu cũ chưa xử lý | Rất cao | Consent withdrawal, delete/anonymize workflow |
| Model drift sau go-live | Cao | Theo dõi false alert/missed detection, retrain plan |
| Staging khác production | Cao | Staging-production parity checklist |
| Một developer khó bàn giao | Cao | Docs, runbook, README, code convention |

## Go-live checklist

- SRS/use case đã được xác nhận.
- Consent/privacy đã được nhà trường duyệt.
- Tài khoản cá nhân, MFA cho Admin/BGH.
- Web/Mobile route guard hoạt động.
- Backend permission test pass.
- ANSVIS trigger hoạt động với payload đã kiểm soát.
- Object storage private, signed URL.
- Không có secret trong repo.
- Backup/restore đã test.
- Monitoring/alert đã bật.
- Có incident response runbook.
