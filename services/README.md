# Services

Chứa API Gateway và backend service theo domain khi một issue triển khai cụ thể yêu cầu.

- Mỗi service sở hữu business boundary và PostgreSQL schema của mình.
- Không đọc trực tiếp schema của service khác; tích hợp qua API, event hoặc shared contract.
- Domain rules không phụ thuộc framework, database, queue, storage hoặc ANSVIS client.
- Mỗi service phải có README, environment example, migration và test phù hợp với rủi ro.

Service hiện có:

- `api-gateway/`: entry point FastAPI tối thiểu, health check, request correlation và error envelope.
- `identity-service/`: internal Identity boundary cho user/role/permission/session metadata an toàn.
- `school-service/`: owner của tám bảng `school`, migration và constraint tenant/lifecycle an toàn.
- `audit-log-service/`: owner của `audit.audit_events`, validation, idempotency và integrity chain
  append-only.

API Gateway và Identity Service hiện chưa có business route, auth flow, proxy, database hay ANSVIS
integration. School Service mới chỉ có schema/migration, chưa có API/repository/decryption. Audit Log
Service chỉ nhận event qua application boundary và chưa có query/export API hoặc retention executor.
Các khả năng đó chỉ được bổ sung bởi issue riêng với authorization và data-boundary tests tương ứng.
Web và Mobile không được gọi các internal service trực tiếp.
