# Services

Chứa API Gateway và backend service theo domain khi một issue triển khai cụ thể yêu cầu.

- Mỗi service sở hữu business boundary và PostgreSQL schema của mình.
- Không đọc trực tiếp schema của service khác; tích hợp qua API, event hoặc shared contract.
- Domain rules không phụ thuộc framework, database, queue, storage hoặc ANSVIS client.
- Mỗi service phải có README, environment example, migration và test phù hợp với rủi ro.

Scaffold này chưa tạo deployable service hoặc xử lý dữ liệu nghiệp vụ.
