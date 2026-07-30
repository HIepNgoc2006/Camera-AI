# Code-coupled documentation

Chứa tài liệu cần phát hành cùng implementation, như OpenAPI/event schema, ADR, service runbook và thay đổi cấu hình/vận hành.

- Không sao chép bulk planning, executive material hoặc reference asset vào code repository.
- Cập nhật tài liệu khi code thay đổi API, schema, security behavior, environment hoặc operations.
- Không chứa secret, dữ liệu thật, raw ANSVIS payload, ảnh/video evidence hoặc thông tin định danh thật.

Planning và tài liệu tham chiếu local tiếp tục được giữ ngoài implementation commits.

Runbook hiện có:

- `nfr-baseline.md`: baseline NFR sanitized cho load/capacity, latency, availability và RPO/RTO.
- `security-baseline.md`: baseline security sanitized cho data classification, authorization,
  encryption/lookup, rate limit, retention và audit.
- `quality-gates.md`: lệnh lint, typecheck, unit test và repository policy dùng local/CI.
- `../packages/ansvis-event-contract/README.md`: contract HTTP Trigger JSON/ACK, auth, replay và
  idempotency versioned cho ANSVIS integration.
- `project-progress.md`: báo cáo tiến độ live, execution-lane policy và lịch sử workflow hằng tuần.
- `operations/time-synchronization-policy.md`: UTC/IANA, clock drift và replay-window contract cho
  Backend/ANSVIS/PostgreSQL.
- `operations/queue-backpressure-dlq-policy.md`: threshold table, circuit
  closed/open/half-open, DLQ quarantine/replay và rollback an toàn.
- `operations/deployment-capacity-baseline.md`: topology sanitized, resource/connection budget,
  split/growth trigger và Compose enforcement cho #96.
- `security/fixture-safety.md`: quy tắc fake fixture/seed, scanner và incident response.
- `security/repository-protection.md`: branch protection và required-check baseline.
- `security/secret-scanning.md`: Gitleaks, canary và quy trình xử lý finding.
