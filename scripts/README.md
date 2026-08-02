# Scripts

Chứa script có thể review để build, test, lint, migrate, deploy, backup và vận hành hệ thống.

- Script phải có safe default, input validation và exit code rõ.
- Không hard-code hoặc in secret, credentialed URL hay dữ liệu nhạy cảm.
- Thao tác phá hủy phải xác minh target, nêu phạm vi ảnh hưởng và yêu cầu approval phù hợp.
- Script liên quan database hoặc local Docker data phải tuân thủ migration, backup và path-safety rules.

Các entry point hiện có:

- `quality.py`: chạy repository/security policy, Ruff, Mypy và unit tests bằng một lệnh ổn định.
- `check_security_scanning_policy.py`: kiểm tra scanner pin, audit inventory, exception expiry,
  automation files và fail-closed image/SBOM activation gate.
- `test_security_scanners_canary.py`: tạo canary giả lập trong `.local/tmp`, bỏ scanner output và xác
  minh pip-audit/Bandit/OpenGrep/Trivy thực sự từ chối.
- `check_foundation_safety.py`: kiểm structure, local links, ignore coverage và fail-closed defaults.
- `check_compose_safety.py`: kiểm topology Compose tĩnh mà không khởi động/xóa container.
- `check_fixture_safety.py`: từ chối fixture/seed nhạy cảm và chỉ báo category + path.
- `test_fixture_safety_canary.py`: xác minh fake violation bị chặn mà không in nội dung.
- `check_repository_safety.py`: kiểm tra tên/kích thước file tracked mà không đọc nội dung.
- `test_gitleaks_canary.py`: xác minh Gitleaks chặn fake canary và không in giá trị scanner.
- `project_status.py`: tổng hợp tiến độ live từ metadata GitHub/Git, hỗ trợ text/JSON và kiểm tra
  execution-lane policy mà không đọc issue body hoặc log workflow.
- `check_time_policy.py`: kiểm machine-readable time policy và fixture UTC/IANA/drift/replay giả lập.
- `check_evidence_access_policy.py`: kiểm role/object/purpose/consent/retention, signed GET TTL,
  export/audit và ma trận allow/deny evidence giả lập mà không tạo URL hoặc đọc media.
- `check_notification_privacy_policy.py`: kiểm channel/content minimization, recipient/object/purpose,
  endpoint protection, retry/DLQ, cancellation/open re-authorization và audit bằng dữ liệu giả lập;
  không tạo notification, provider call hoặc đọc endpoint/token thật.
- `check_consent_withdrawal_policy.py`: kiểm authority/maturity, state precedence,
  deny-before-dispose, owner disposition, legal hold/lawful basis, retry/reconciliation, restore và
  completion evidence bằng dữ liệu giả lập; không xóa/anonymize record, gọi provider hoặc đọc dữ liệu
  thật.
- `check_api_contract.py`: kiểm OpenAPI v1, error registry, authorization catalog, năm control bảo
  mật trên từng operation, rate-limit bucket và client-generation smoke; không khởi tạo route hoặc
  gọi dịch vụ runtime.
- `check_ansvis_event_contract.py`: kiểm JSON Schema, Bearer source auth/replay/idempotency/ACK policy
  và ma trận contract ANSVIS giả lập mà không in payload bị từ chối.
- `check_metrics_registry.py`: kiểm registry `metrics_registry_v1` — baseline metric đầy đủ,
  cardinality trong giới hạn, label không mang identifier, bucket histogram tăng dần; chỉ in tên
  metric và số lượng.
- `check_web_bff_session_policy.py`: kiểm boundary Browser/BFF/API Gateway/Identity, server-only token
  custody, cookie, CSRF/origin, redirect, session/MFA/expiry/revocation state, timeout authority và
  synthetic negative canary; không tạo/đọc cookie, token, secret, credential hoặc session thật.

Xem `docs/quality-gates.md`, `docs/project-progress.md`,
`docs/security/repository-protection.md`, `docs/security/secret-scanning.md` và
`docs/security/supply-chain-scanning.md` để cài tool và chạy local.
