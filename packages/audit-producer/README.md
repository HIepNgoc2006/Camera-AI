# audit-producer

Thư viện dùng chung cho phía **phát** audit intent (Issue #138). Service chủ sở hữu hành động nhạy
cảm build một `AuditIntent` (shape-validated, minimized) và ghi vào outbox riêng của mình qua port
`AuditIntentRecorder`; worker giao hàng bind `TrustedAuditContext` và append vào
`audit.audit_events` của audit-log-service — nơi `validate_action_policy` (registry action đã
duyệt) vẫn là thẩm quyền cuối.

## Nguyên tắc

- Mọi field là stable code/UUID/count/timestamp có bound — free text, media, token, secret,
  giá trị cá nhân **không thể** xuất hiện về mặt cấu trúc.
- `result=denied|failed` bắt buộc `reason_code` (khớp domain rule của audit-log-service).
- Actor/school/retention KHÔNG nằm trong publisher payload — chúng thuộc trusted context tại
  delivery (school scope truyền qua cột riêng của outbox).
- `UnavailableAuditIntentRecorder` là default fail-closed: service chưa wire outbox không thể
  giả vờ đã audit.
- Idempotency: dedupe theo `(source_service, source_event_id)` ở transport outbox và một lần nữa
  ở audit store (duplicate = success-already-recorded).

## Sử dụng

```python
from camera_ai_audit import AuditIntent, IntentResult

intent = AuditIntent(
    source_service="ansvis-adapter-service",
    source_event_id=event_uuid,
    action="ANSVIS_SOURCE_AUTH_DENIED",
    resource_type="ansvis_source",
    request_id=request_id,
    result=IntentResult.DENIED,
    reason_code="EVENT_SOURCE_UNAUTHORIZED",
    occurred_at=now_utc,
)
recorder.record(intent)  # PostgresAuditOutbox của service, idempotent
```

## Test

```powershell
rtk .\.venv\Scripts\python.exe -m pytest -q packages/audit-producer/tests
```
