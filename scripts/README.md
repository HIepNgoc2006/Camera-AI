# Scripts

Chứa script có thể review để build, test, lint, migrate, deploy, backup và vận hành hệ thống.

- Script phải có safe default, input validation và exit code rõ.
- Không hard-code hoặc in secret, credentialed URL hay dữ liệu nhạy cảm.
- Thao tác phá hủy phải xác minh target, nêu phạm vi ảnh hưởng và yêu cầu approval phù hợp.
- Script liên quan database hoặc local Docker data phải tuân thủ migration, backup và path-safety rules.

Các entry point hiện có:

- `quality.py`: chạy repository policy, Ruff, Mypy và unit tests bằng một lệnh ổn định.
- `check_foundation_safety.py`: kiểm structure, local links, ignore coverage và fail-closed defaults.
- `check_compose_safety.py`: kiểm topology Compose tĩnh mà không khởi động/xóa container.
- `check_fixture_safety.py`: từ chối fixture/seed nhạy cảm và chỉ báo category + path.
- `test_fixture_safety_canary.py`: xác minh fake violation bị chặn mà không in nội dung.
- `check_repository_safety.py`: kiểm tra tên/kích thước file tracked mà không đọc nội dung.
- `test_gitleaks_canary.py`: xác minh Gitleaks chặn fake canary và không in giá trị scanner.
- `project_status.py`: tổng hợp tiến độ live từ metadata GitHub/Git, hỗ trợ text/JSON và kiểm tra
  execution-lane policy mà không đọc issue body hoặc log workflow.

Xem `docs/quality-gates.md`, `docs/project-progress.md`,
`docs/security/repository-protection.md` và `docs/security/secret-scanning.md` để cài tool và chạy
local.
