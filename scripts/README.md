# Scripts

Chứa script có thể review để build, test, lint, migrate, deploy, backup và vận hành hệ thống.

- Script phải có safe default, input validation và exit code rõ.
- Không hard-code hoặc in secret, credentialed URL hay dữ liệu nhạy cảm.
- Thao tác phá hủy phải xác minh target, nêu phạm vi ảnh hưởng và yêu cầu approval phù hợp.
- Script liên quan database hoặc local Docker data phải tuân thủ migration, backup và path-safety rules.

Scaffold này chưa thêm executable script.
