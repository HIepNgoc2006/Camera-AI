# Technical architecture, data and API

## Kiến trúc triển khai

Hệ thống dùng kiến trúc microservices-ready. Giai đoạn đầu có thể triển khai dạng monorepo/Docker Compose để giảm độ phức tạp, nhưng service boundary vẫn phải rõ để dễ mở rộng.

```text
Web Portal / Mobile App / ANSVIS HTTP Trigger
              |
          API Gateway
              |
 Identity / School / Consent / Camera / ANSVIS Adapter
              |
 Event Ingestion + RabbitMQ/Outbox + Workers
              |
 Attendance / Timekeeping / Violation / Notification / Report
              |
 PostgreSQL / Redis / Object Storage / Audit / Monitoring
```

## Thành phần kỹ thuật

| Thành phần | Vai trò |
|---|---|
| API Gateway | Điểm vào duy nhất, auth middleware, rate limit, CORS |
| Backend services | Xử lý nghiệp vụ, phân quyền, dữ liệu |
| Workers | Xử lý event AI, notification, report bất đồng bộ |
| PostgreSQL | Database nghiệp vụ chính |
| Redis | Cache, rate limit, lock |
| RabbitMQ | Queue event/retry/DLQ |
| Object Storage | Ảnh/video evidence, model artifact |
| ANSVIS/AIBOX | AI video analytics và event trigger |
| Web Portal | Dashboard và quản trị |
| Mobile App | Ứng dụng phụ huynh/giáo viên/BGH |
| Monitoring | Log, metric, alert, tracing |

## Database/ERD mức module

| Nhóm bảng/schema | Dữ liệu chính |
|---|---|
| Identity | user, role, permission, session, MFA |
| School | student, parent, teacher, class, assignment |
| Privacy | consent, purpose, retention policy |
| Camera | camera, zone, status, ANSVIS mapping |
| Integration | source system, trigger config, payload version |
| Events | raw metadata, normalized event, idempotency key |
| Attendance | check-in/out, attendance status, review |
| Timekeeping | staff record, shift, correction |
| Violation | violation record, evidence, review status |
| Notification | template, recipient, delivery log |
| Evidence | object key, signed URL policy, retention |
| Reporting | dashboard snapshot, materialized views |
| AI Registry | dataset, model, experiment, metric |
| Audit | append-only action log |

## Database decision

PostgreSQL là database chính vì dữ liệu trường học có quan hệ chặt, cần transaction, audit và báo cáo rõ. JSONB có thể dùng để lưu payload ANSVIS đã kiểm soát. MongoDB không khuyến nghị làm database nghiệp vụ chính; chỉ cân nhắc sau này cho analytics/event volume đặc biệt nếu cần.

## Database and encryption baseline

| Hạng mục | Quy định |
|---|---|
| Database chính | PostgreSQL, chia schema theo domain |
| Media evidence | Không lưu binary trong PostgreSQL; lưu ở private object storage |
| Signed URL | TTL ngắn, tạo sau khi kiểm tra quyền, có audit |
| Dữ liệu sinh trắc học | Chỉ xử lý khi có consent; nếu lưu embedding phải mã hóa và có `key_id` |
| Secret/key | Lưu ở secret manager/KMS, không lưu trong Git/database business |
| Backup | PostgreSQL/object storage/model artifact backup phải mã hóa và restore thử |
| Retention | Mỗi nhóm dữ liệu có thời hạn lưu, xóa hoặc ẩn danh |
| Audit | Xem/sửa/xóa/export dữ liệu nhạy cảm đều phải ghi audit |

## API nhóm chức năng

| Nhóm API | Ví dụ |
|---|---|
| Auth | login, logout, refresh, MFA, revoke session |
| User/Role | user, role, permission, assignment |
| School | student, parent, teacher, class |
| Consent | create/update consent, check consent status |
| Camera | camera list, zone, status, ANSVIS mapping |
| ANSVIS Webhook | receive event, test trigger, health check |
| Attendance | attendance status, event detail, correction |
| Timekeeping | staff check-in/out, report |
| Violation | list/detail/review/resolve violation |
| Notification | notification list, delivery status |
| Report | dashboard, export with audit |
| Audit | audit search by authorized role |
| Operations | health, metrics, backup status |

## API security rules

- Tất cả API cần auth trừ endpoint health/public được cho phép.
- API dữ liệu học sinh/sự kiện phải có object-level authorization.
- Endpoint export phải audit.
- Webhook ANSVIS phải validate token/HMAC/source/schema.
- Error response có mã lỗi ổn định, không trả stack trace.
- Rate limit cho login, export, webhook và notification.

## Deployment architecture

| Môi trường | Mục tiêu |
|---|---|
| Local | Dev bằng Docker Compose, mock ANSVIS payload |
| Staging | Test tích hợp, dữ liệu giả lập, UAT nội bộ |
| Pilot | Chạy thử với một phần camera thật, shadow mode |
| Production | Chạy chính thức, backup, monitoring, alert |

## Infrastructure and performance

| Hạng mục | Yêu cầu |
|---|---|
| ANSVIS/AIBOX | Máy vật lý/GPU/license phù hợp theo tài liệu ANSCENTER |
| Backend | Có thể scale worker/event ingestion |
| Database | Backup, migration, index, partition event nếu tải cao |
| Storage | Private bucket, lifecycle, signed URL |
| Queue | Retry, dead-letter queue, monitor backlog |
| Monitoring | API latency, error rate, queue depth, storage, ANSVIS task |
| Backup | PostgreSQL, object storage, model artifact, ANSVIS config |

## Tích hợp ANSVIS

Backend không đọc trực tiếp camera nếu ANSVIS/AIBOX là tầng AI chính. ANSVIS xử lý video và gửi event qua HTTP Trigger. Backend nhận event, validate, chuẩn hóa và xử lý nghiệp vụ.
