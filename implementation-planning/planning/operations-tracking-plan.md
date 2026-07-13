# Operations, tracking and support plan

## Theo dõi tiến độ

Task nên theo format:

| Field | Nội dung |
|---|---|
| ID | `BE-001`, `AI-001`, `SEC-001`, `WEB-001`, `MOB-001`, `QA-001`, `OPS-001` |
| Title | Tên task ngắn |
| Type | Feature/Bug/Security/Docs/Ops |
| Scope | Service/module |
| Priority | Critical/High/Medium/Low |
| Dependency | Task cần xong trước |
| DoD | Definition of Done |
| Evidence | Test/log/screenshot/report |

Vì chỉ có một developer, task phải có phụ thuộc tuần tự rõ ràng.

## Bug tracking

Bug ticket cần có:

- Môi trường: local/staging/production.
- User role.
- Steps reproduce.
- Expected/actual.
- Request ID/event ID nếu có.
- Dữ liệu có nhạy cảm không.
- Log đã masking.
- Severity.
- Root cause sau khi fix.

## Security issue tracking

Security ticket cần có:

- Dữ liệu bị ảnh hưởng.
- Khả năng khai thác.
- Ảnh hưởng.
- Biện pháp tạm thời.
- Fix dài hạn.
- Secret cần rotate hay không.
- Có cần thông báo nhà trường/phụ huynh hay không.

## Logging/observability

Log bắt buộc có:

- `request_id`
- `service_name`
- `environment`
- `actor_id` nếu có
- `event_id`/`correlation_id` nếu là AI event
- mã lỗi ổn định

Không log:

- Password/token/key.
- RTSP URL có credential.
- Face embedding.
- Image base64.
- Payload raw có ảnh/video/biometric.

Metric cần theo dõi:

- API latency/error rate.
- Event ingestion rate.
- Queue depth/DLQ count.
- ANSVIS task status/process time.
- Storage usage.
- Login fail/export spike.
- Worker retry/failure.

## Backup/restore

Backup cần bao gồm:

- PostgreSQL.
- Object storage evidence.
- Model artifact.
- Dataset manifest.
- ANSVIS config/restore point.
- Face DB nếu được phép và có quy trình bảo mật.

Lưu ý từ tài liệu ANSVIS: restore point có thể không bao gồm uploaded files, user model, face DB và license DB. Vì vậy không được coi ANSVIS backup là backup đầy đủ cho toàn hệ thống.

## Support/SLA đề xuất

| Mức | Ví dụ | Phản hồi |
|---|---|---|
| Critical | Rò rỉ dữ liệu, sai phân quyền, hệ thống dừng | Ngay khi nhận |
| High | Mất event, không điểm danh được, notification sai | Trong ngày |
| Medium | Report sai, UI lỗi flow phụ | Theo lịch xử lý |
| Low | Cải tiến nhỏ | Gom theo release |

## Runbook tối thiểu

- Cách kiểm tra hệ thống sống.
- Cách kiểm tra ANSVIS task.
- Cách kiểm queue backlog.
- Cách kiểm storage sắp đầy.
- Cách revoke user/token.
- Cách rotate secret.
- Cách restore database.
- Cách rollback release.
- Cách tắt tạm notification/AI event nếu lỗi hàng loạt.\n