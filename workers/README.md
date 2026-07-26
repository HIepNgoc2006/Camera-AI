# Workers

Chứa queue consumer, scheduled job và xử lý bất đồng bộ đã được tách khỏi request path.

- Event consumer phải idempotent, có retry giới hạn và DLQ khi áp dụng.
- Không ghi raw media, biometric payload, token hoặc credential vào log/queue.
- Worker truy cập dữ liệu qua ownership boundary được phê duyệt; không đọc chéo schema.
- Mỗi worker cần health signal, test và rollback/disable path.

Worker runtime hiện có:

- `event-outbox-worker/` (Issue #135): drain outbox của `services/ansvis-adapter` — batch claim 50
  message bằng `FOR UPDATE SKIP LOCKED`, publish sang RabbitMQ exchange topic durable
  `camera-ai.events.v1` dưới publisher confirms, acknowledge cả batch một lần; broker outage không
  đốt retry attempt; SIGINT/SIGTERM dừng graceful sau batch đang xử lý. Xem README của worker để
  biết env, topology và lệnh chạy/test.
