# event-outbox-worker

Supervised drain worker cho outbox của `services/ansvis-adapter` (Issue #135). Claim batch 50
message bằng `FOR UPDATE SKIP LOCKED`, publish sang RabbitMQ dưới publisher confirms, acknowledge
cả batch một lần; retry/dead-letter đúng policy `normalized_outbox_v1`.

## Topology (pinned)

| Thành phần | Giá trị |
|---|---|
| Exchange | `camera-ai.events.v1`, type `topic`, durable |
| Routing key | topic của normalized event (vd `camera_ai.events.camera_health_changed.v1`) |
| Message | JSON canonical (sort_keys), `content_type=application/json`, `delivery_mode=2` |
| Confirms | bắt buộc (`confirm_delivery`) |
| Queue/binding/DLX | thuộc consumer; worker không declare |

## Env

| Biến | Bắt buộc | Ghi chú |
|---|---|---|
| `EVENT_DATABASE_URI` | có | `postgresql+psycopg://...` — dùng chung contract với ansvis-adapter |
| `EVENT_BROKER_URI` | có | `amqp://` local/test; `amqps://` bắt buộc ở staging/production; cấm placeholder |
| `WORKER_BATCH_SIZE` | không | 1..50, mặc định 50 |
| `WORKER_IDLE_SLEEP_SECONDS` | không | 0.1..60, mặc định 1 |
| `WORKER_BROKER_RETRY_SECONDS` | không | 1..300, mặc định 5 |
| `WORKER_METRICS_PORT` | không | 0 = tắt; mặc định 9465 (0 khi `APP_ENV=test`); scrape chỉ bind 127.0.0.1 |
| `WORKER_SNAPSHOT_INTERVAL_SECONDS` | không | 5..3600, mặc định 60 — chu kỳ cập nhật gauge backlog/oldest-age và đánh giá alert |
| `EVENT_DB_POOL_SIZE` / `EVENT_DB_MAX_OVERFLOW` | không | mặc định `2 + 1`; event-store pool của mỗi worker process |
| `AUDIT_DB_POOL_SIZE` / `AUDIT_DB_MAX_OVERFLOW` | không | mặc định `1 + 0`; audit-store pool của mỗi worker process |
| `DB_POOL_TIMEOUT_SECONDS` | không | 0.1..30, mặc định 2; fail nhanh để backpressure thay vì chờ connection vô hạn |
| `APP_ENV`, `LOG_LEVEL` | không | như các service khác |

Tổng `pool_size + max_overflow` của hai database trong một worker process bị khóa ở tối đa 4.
Baseline chạy hai replica do đó dùng tối đa 8 PostgreSQL connections; mọi thay đổi phải giữ tổng
budget trong [deployment-capacity-baseline.md](../../docs/operations/deployment-capacity-baseline.md)
và được kiểm chứng bằng burst profile #95.

Metrics (registry `metrics_registry_v1`): counters dispatch/replay/alerts, histogram
`event_outbox_enqueue_to_publish_seconds`, gauges `event_outbox_backlog_messages` và
`event_outbox_oldest_pending_seconds`. Alert `EVENT_OUTBOX_DLQ_UNTRIAGED` và
`EVENT_OUTBOX_OLDEST_MESSAGE` (120s warning / 600s critical) được đánh giá mỗi chu kỳ snapshot,
log bằng stable code và đếm vào `event_operational_alerts_total`.

## Audit delivery (Issue #138)

Cùng vòng drain, worker giao audit intent từ `events.audit_outbox` (adapter ghi) vào
`audit.audit_events` qua `AppendAuditEventService` của audit-log-service:

- Trusted context bind tại delivery: `actor_type=service`, retention `AUDIT_RETENTION_DAYS`
  (mặc định 1825 ngày), school scope từ cột outbox.
- Duplicate append = success-already-recorded (không retry storm, không double evidence).
- Dead-letter transition của event outbox được audit **trước khi persist**
  (`EVENT_PROCESSING_DEAD_LETTERED`): audit outbox không ghi được ⇒ transition bị hủy, lease hết
  hạn và thử lại — không có dead-letter nào không có bằng chứng.
- Consent fan-out guard (Issue #139): message face/emotion mà payload không chứng minh
  `consent_gate_status ∈ {allowed, not_required}` bị từ chối vĩnh viễn (`publish_status=refused`,
  attempt `consent-guard`/`EVENT_CONSENT_BLOCKED`), audit `EVENT_CONSENT_DENIED` **trước khi
  persist** với identity xác định theo outbox message — replay không thể biến event bị chặn thành
  business record. Store của worker wire `UnavailableConsentGate` (drain-only, không ghi event).
- Env bổ sung: `AUDIT_DATABASE_URI` (bắt buộc), `AUDIT_INTEGRITY_KEY` (≥32 byte, cấm placeholder
  ngoài local/test), `AUDIT_RETENTION_DAYS` (30..3650). Gauge
  `event_audit_outbox_oldest_pending_seconds` cảnh báo tồn đọng theo ngưỡng #35 (60s warning).

## Hành vi an toàn

- Broker chưa kết nối được ⇒ không claim message nào (không đốt attempt), chờ
  `WORKER_BROKER_RETRY_SECONDS` rồi thử lại.
- Publish lỗi ⇒ message đó retry/dead-letter theo policy; message khác trong batch không bị chặn.
- Publish dùng `mandatory=True` cùng confirms: thiếu binding hoặc broker trả unroutable không
  được đánh dấu published; đi qua cùng retry/dead-letter và stable masked error. Consumers vẫn
  chịu trách nhiệm queues/bindings. Reset/shutdown đóng cả channel và connection sở hữu.
- Composite drain cộng cả `refused` để event bị consent guard chặn vẫn reconcile đủ tổng batch.
- SIGINT/SIGTERM ⇒ hoàn tất batch hiện tại, thoát mã 0; crash cứng ⇒ lease 30s hết hạn và message
  được worker khác claim lại.
- Log chỉ chứa metadata allowlisted + counter; không payload, không broker URL, không identifier.
- Worker không ghi event, không resolve scope, không đụng retention; các port ghi được wire
  fail-closed.

## Chạy và test

```powershell
rtk .\.venv\Scripts\python.exe -m event_outbox_worker
rtk .\.venv\Scripts\python.exe -m pytest -q workers/event-outbox-worker/tests
```

Integration test batch drain nằm ở
`services/ansvis-adapter/tests/integration/test_event_store.py` (gate bằng `EVENT_DATABASE_URI`,
chạy trong CI); smoke end-to-end với broker thật yêu cầu compose profile RabbitMQ qua Docker MCP.
