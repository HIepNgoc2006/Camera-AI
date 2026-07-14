# Code-coupled documentation

Chứa tài liệu cần phát hành cùng implementation, như OpenAPI/event schema, ADR, service runbook và thay đổi cấu hình/vận hành.

- Không sao chép bulk planning, executive material hoặc reference asset vào code repository.
- Cập nhật tài liệu khi code thay đổi API, schema, security behavior, environment hoặc operations.
- Không chứa secret, dữ liệu thật, raw ANSVIS payload, ảnh/video evidence hoặc thông tin định danh thật.

Planning và tài liệu tham chiếu local tiếp tục được giữ ngoài implementation commits.

Runbook hiện có:

- `quality-gates.md`: lệnh lint, typecheck, unit test và repository policy dùng local/CI.
- `security/secret-scanning.md`: Gitleaks, canary và quy trình xử lý finding.
