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
| `APP_ENV`, `LOG_LEVEL` | không | như các service khác |

Metrics (registry `metrics_registry_v1`): counters dispatch/replay/alerts, histogram
`event_outbox_enqueue_to_publish_seconds`, gauges `event_outbox_backlog_messages` và
`event_outbox_oldest_pending_seconds`. Alert `EVENT_OUTBOX_DLQ_UNTRIAGED` và
`EVENT_OUTBOX_OLDEST_MESSAGE` (120s warning / 600s critical) được đánh giá mỗi chu kỳ snapshot,
log bằng stable code và đếm vào `event_operational_alerts_total`.

## Hành vi an toàn

- Broker chưa kết nối được ⇒ không claim message nào (không đốt attempt), chờ
  `WORKER_BROKER_RETRY_SECONDS` rồi thử lại.
- Publish lỗi ⇒ message đó retry/dead-letter theo policy; message khác trong batch không bị chặn.
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
