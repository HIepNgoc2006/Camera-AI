# Workers

Chứa queue consumer, scheduled job và xử lý bất đồng bộ đã được tách khỏi request path.

- Event consumer phải idempotent, có retry giới hạn và DLQ khi áp dụng.
- Không ghi raw media, biometric payload, token hoặc credential vào log/queue.
- Worker truy cập dữ liệu qua ownership boundary được phê duyệt; không đọc chéo schema.
- Mỗi worker cần health signal, test và rollback/disable path.

Scaffold này chưa tạo worker runtime.
