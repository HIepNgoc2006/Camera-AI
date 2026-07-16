# Services

Chứa API Gateway và backend service theo domain khi một issue triển khai cụ thể yêu cầu.

- Mỗi service sở hữu business boundary và PostgreSQL schema của mình.
- Không đọc trực tiếp schema của service khác; tích hợp qua API, event hoặc shared contract.
- Domain rules không phụ thuộc framework, database, queue, storage hoặc ANSVIS client.
- Mỗi service phải có README, environment example, migration và test phù hợp với rủi ro.

Service hiện có:

- `api-gateway/`: entry point FastAPI tối thiểu, health check, request correlation và error envelope.
- `identity-service/`: internal Identity boundary cho user/role/permission/session metadata an toàn.

Hai service hiện chưa có business route, auth flow, proxy, database hay ANSVIS integration. Các khả
năng đó chỉ được bổ sung bởi issue riêng với authorization và data-boundary tests tương ứng. Web và
Mobile không được gọi Identity Service trực tiếp.
