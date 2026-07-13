# Architecture, database, tools and libraries

## Kiến trúc mục tiêu

Kiến trúc đề xuất là microservices-ready monorepo: code được tách theo service rõ ràng, nhưng giai đoạn đầu có thể deploy bằng Docker Compose để giảm độ phức tạp vận hành cho một developer.

```text
Web Portal / Mobile App / ANSVIS HTTP Trigger
              |
          API Gateway
              |
  Identity / School / Consent / Camera / ANSVIS Adapter
              |
      Event Ingestion + RabbitMQ + Outbox
              |
 Attendance / Timekeeping / Violation / Notification / Report
              |
 PostgreSQL / Redis / Object Storage / Audit / Monitoring
```

## Service boundary

| Service | Trách nhiệm |
|---|---|
| API Gateway | Route, auth middleware, rate limit, request ID, CORS |
| Identity Service | User, role, permission, MFA, session/token |
| School Service | Học sinh, phụ huynh, giáo viên, lớp |
| Consent Service | Đồng ý xử lý dữ liệu, mục đích, retention |
| Camera Registry | Metadata camera, vùng lắp đặt, credential reference |
| ANSVIS Adapter | Nhận HTTP Trigger, validate payload, normalize event |
| Event Ingestion | Idempotency, raw metadata, outbox/queue |
| Attendance Service | Điểm danh học sinh |
| Timekeeping Service | Chấm công cán bộ/giáo viên |
| Violation Service | Vi phạm đồng phục, đi trễ, xả rác, hút thuốc, bảo hộ |
| Notification Service | Push/in-app/email, template, delivery log |
| Report Service | Dashboard, thống kê, export |
| Evidence Storage | Metadata ảnh/video, signed URL |
| AI Model Registry | Dataset, model version, metric, approval |
| Audit Log Service | Append-only audit cho thao tác nhạy cảm |

## Database strategy

Khuyến nghị dùng PostgreSQL làm database chính, không dùng MongoDB làm primary database.

Lý do:

- Dữ liệu trường học có quan hệ chặt: học sinh, phụ huynh, lớp, giáo viên, điểm danh, phân quyền.
- Cần transaction và audit rõ ràng.
- Cần báo cáo chính xác.
- PostgreSQL có JSONB để lưu payload ANSVIS linh hoạt khi cần.

Schema đề xuất:

| Schema | Dữ liệu |
|---|---|
| `identity` | user, role, permission, session, MFA |
| `school` | student, parent, teacher, class |
| `privacy` | consent, purpose, retention |
| `camera` | camera metadata, zone, credential reference |
| `integration` | ANSVIS source, trigger config |
| `events` | raw/normalized event, idempotency |
| `attendance` | điểm danh |
| `timekeeping` | chấm công |
| `violation` | vi phạm |
| `notification` | thông báo |
| `reporting` | dashboard/read model |
| `evidence` | ảnh/video metadata |
| `ai_registry` | dataset/model/experiment |
| `audit` | audit log |

MongoDB chỉ nên cân nhắc sau này cho event analytics khối lượng lớn nếu PostgreSQL không còn phù hợp.

## Stack khuyến nghị

| Nhóm | Công cụ/thư viện | Vai trò |
|---|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic | API, service, migration |
| Worker | Python worker + aio-pika/Celery/RQ | Xử lý event, notification, report job |
| Database | PostgreSQL 16+ | Dữ liệu nghiệp vụ chính |
| Cache | Redis 7+ | Cache, rate limit, lock |
| Queue | RabbitMQ | Event AI, retry, DLQ |
| Object storage | MinIO hoặc S3-compatible | Ảnh/video evidence, model artifact, backup |
| Web | Next.js, React, TypeScript, Tailwind/shadcn hoặc Ant Design | Portal |
| Mobile | React Native, React Navigation, TanStack Query | App iOS/Android |
| Mobile secure | expo-secure-store hoặc react-native-keychain | Lưu token |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Sentry | Log, metric, trace, crash |
| Security scan | gitleaks, Semgrep, pip-audit, npm audit, Trivy, OWASP ZAP | Kiểm tra bảo mật |
| AI | ANSVIS Face Detection/Facial Recognition; ANSTS/ODHUB nếu cần custom pipeline; OpenCV/FFmpeg hỗ trợ | Face attendance/timekeeping, Littering, Smoking, Student Uniform, Kitchen PPE |

## Folder structure gọn

```text
camera-ai-platform/
  apps/
    web-portal/
    mobile-app/
  services/
    api-gateway/
    identity-service/
    school-service/
    consent-service/
    camera-registry-service/
    ansvis-adapter-service/
    event-ingestion-service/
    attendance-service/
    timekeeping-service/
    violation-service/
    notification-service/
    report-service/
    evidence-storage-service/
    ai-model-registry-service/
    audit-log-service/
  workers/
    event-worker/
    notification-worker/
    report-worker/
  packages/
    shared-contracts/
    shared-security/
    shared-observability/
  infra/
    docker/
    nginx/
    postgres/
    rabbitmq/
    monitoring/
  docs/
  scripts/
  .env.example
  AGENTS.md
```

## Deployment mode

| Môi trường | Cách chạy |
|---|---|
| Local | Docker Compose + mock ANSVIS payload |
| Staging | Docker Compose/VM riêng, dữ liệu giả lập |
| Pilot | Server thật, một phần camera, shadow mode |
| Production | Server kiểm soát, backup, monitoring, alert |
