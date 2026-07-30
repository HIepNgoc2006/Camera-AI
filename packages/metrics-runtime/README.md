# metrics-runtime

Registry metric `metrics_registry_v1` và Prometheus sink dùng chung cho mọi process Camera AI
(Issue #136). Đây là nguồn duy nhất của vocabulary metric: emit tên/label ngoài registry sẽ raise
`ValueError` (call site nuốt lỗi metric nên telemetry không bao giờ phá request/drain path).

## Nguyên tắc

- Mỗi metric khai báo kind (counter/histogram/gauge), help text, và — với counter — **toàn bộ**
  tập giá trị label `outcome` được phép (≤ 8 giá trị, snake_case). Label không bao giờ chứa
  tenant/camera/subject/event identifier ⇒ cardinality bị chặn từ cấu trúc.
- Suffix theo kind: `_total` (counter), `_seconds` (histogram), `_seconds|_messages` (gauge).
- Mỗi `PrometheusMetricsSink` sở hữu `CollectorRegistry` riêng ⇒ app factory chạy nhiều lần trong
  test không đụng độ.
- `/metrics` expose qua `start_internal_metrics_server` — **chỉ bind loopback**, từ chối mọi
  địa chỉ non-loopback; không bao giờ đi qua API Gateway.

## Thêm metric mới

1. Thêm `MetricSpec` vào `registry.py` (structural validation chạy ngay khi import).
2. Cập nhật `BASELINE_METRICS` trong `scripts/check_metrics_registry.py` (checker fail nếu lệch).
3. Emit qua port `MetricsSink` (`increment`/`observe`/`set_gauge`).

## Queue policy

`src/camera_ai_metrics/queue_policy_v1.json` là bảng threshold duy nhất cho queue depth,
drain ETA, DLQ, oldest-unpublished, circuit breaker và retry contract. `queue_policy.py` chỉ
phát stable queue/alert codes cùng aggregate count/duration/ratio; không có payload, subject,
endpoint hay identifier. Runbook: `../../docs/operations/queue-backpressure-dlq-policy.md`.

## Test

```powershell
rtk .\.venv\Scripts\python.exe -m pytest -q packages/metrics-runtime/tests
```
