# Services

Chứa API Gateway và backend service theo domain khi một issue triển khai cụ thể yêu cầu.

- Mỗi service sở hữu business boundary và PostgreSQL schema của mình.
- Không đọc trực tiếp schema của service khác; tích hợp qua API, event hoặc shared contract.
- Domain rules không phụ thuộc framework, database, queue, storage hoặc ANSVIS client.
- Mỗi service phải có README, environment example, migration và test phù hợp với rủi ro.

Service hiện có (đây là trạng thái mã nguồn, không đồng nghĩa đã được kích hoạt production):

- `api-gateway/`: FastAPI entry point, health check, request correlation, error envelope và allowlist
  proxy cho các route xác thực của Identity Service; upstream chưa được inject thì fail closed.
- `identity-service/`: internal Identity boundary cho user/role/permission/session, MFA, refresh
  rotation và auth runtime; Web/Mobile chỉ truy cập qua API Gateway.
- `school-service/`: owner của tám bảng `school`, migration và constraint tenant/lifecycle an toàn.
- `audit-log-service/`: owner của `audit.audit_events`, validation, idempotency và integrity chain
  append-only.
- `consent-service/`: owner của purpose/consent trong `privacy`, consent gate fail-closed và
  transactional audit-intent outbox.
- `camera-registry-service/`: owner của camera/zone registry, mapping metadata và lifecycle an toàn.
- `ansvis-adapter/`: HTTP Trigger JSON boundary, strict normalization, PostgreSQL durable receipt,
  minimized `events` schema và transactional outbox; runtime mặc định vẫn từ chối cho tới khi auth,
  authoritative scope resolver, retention policy, database và publisher được nối rõ ràng.
- `attendance-service/`: internal application boundary cho attendance record, event link và correction
  append-only; chưa có public FastAPI route.
- `timekeeping-service/`: internal application boundary cho ca làm, chấm công và correction
  append-only; chưa có public route.
- `notification-service/`: internal, inactive-by-default boundary cho generic in-app/push/email
  intents, fresh recipient authorization, encrypted endpoint references, bounded retry/cancellation
  và transactional audit outbox; chưa có provider adapter hoặc public route.
- `evidence-service/`: policy và internal contract cho metadata, private object storage, signed access
  ngắn hạn, expiry/legal hold; production activation mặc định bị chặn.
- `report-service/`: internal report/export boundary với object-level filtering, aggregate suppression,
  private artifact và re-authorization; production activation mặc định bị chặn.

API Gateway hiện chỉ proxy bề mặt xác thực được allowlist; các business route khác và mọi runtime
provider chưa được phê duyệt vẫn phải fail closed. School Service chưa có API/repository/decryption.
Audit Log Service chưa có query/export API hoặc retention executor. Consent Service chưa có public
API, publisher outbox, retention/DSR executor hoặc biometric processing. Các khả năng còn thiếu chỉ
được bổ sung bởi issue riêng với authorization và data-boundary tests tương ứng.
Web và Mobile không được gọi các internal service trực tiếp.
