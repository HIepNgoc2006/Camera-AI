# Commit, push and pull request rules

## Repo mục tiêu

```text
https://github.com/HIepNgoc2006/Camera-AI
```

## Branch strategy

| Branch | Mục đích | Quy tắc |
|---|---|---|
| `main` | Nhánh ổn định | Không commit trực tiếp nếu đã có codebase chính thức |
| `develop` | Tích hợp trước release | Dùng khi dự án bắt đầu có nhiều module |
| `feature/<scope>-<short-name>` | Tính năng mới | Tạo từ `develop` hoặc `main` tùy giai đoạn |
| `fix/<scope>-<short-name>` | Sửa lỗi | Dùng cho bug thường |
| `security/<scope>-<short-name>` | Sửa vấn đề bảo mật | Ưu tiên cao, review kỹ |
| `docs/<short-name>` | Sửa tài liệu | Dùng cho docs/planning |
| `ops/<short-name>` | DevOps/deploy/config | Không chứa secret thật |

Giai đoạn hiện tại chưa có code production, có thể dùng `main` cho tài liệu. Khi bắt đầu code thật, nên chuyển sang flow: `feature/*` -> PR -> `main` hoặc `develop`.

## Commit message convention

Format:

```text
<type>(<scope>): <short summary>
```

Type:

| Type | Khi dùng |
|---|---|
| `docs` | Tài liệu, plan, README |
| `feat` | Tính năng mới |
| `fix` | Sửa bug |
| `security` | Thay đổi bảo mật |
| `refactor` | Refactor không đổi hành vi |
| `test` | Thêm/sửa test |
| `ops` | Docker, CI/CD, deploy, monitoring |
| `chore` | Việc phụ trợ |

Ví dụ:

```text
docs(github): add issue and push workflow
feat(auth): add MFA setup flow
security(ansvis): validate webhook signature
fix(attendance): prevent duplicate event processing
ops(docker): add local postgres compose service
```

## Push rules

Không push nếu có:

- `.env` thật.
- Secret/key/token/license.
- RTSP URL có username/password.
- Face DB export.
- Dataset, ảnh mặt, video camera thật.
- Database dump thật.
- Log chứa PII/biometric/token.
- File media lớn chưa được duyệt.

Trước khi push cần kiểm:

```powershell
rtk git status
rtk git diff --stat
rtk rg -n "\.env|BEGIN PRIVATE KEY|password=|token=|rtsp://|AKIA|secret" .
```

Khi codebase có tool scan, dùng thêm:

```powershell
gitleaks detect --source .
```

## Pull request rules

PR phải có:

- Mục tiêu thay đổi.
- Issue liên quan.
- Scope ảnh hưởng.
- Security/privacy impact.
- Test/verification đã chạy.
- Screenshot nếu đổi UI.
- Migration note nếu đổi database.
- Rollback note nếu ảnh hưởng production.

Không merge nếu:

- Có secret hoặc dữ liệu thật.
- Test/verification bắt buộc chưa chạy.
- Permission/security check bị bỏ qua.
- PR trộn quá nhiều scope không liên quan.
- Có thay đổi API/schema mà không cập nhật docs.

## Merge rules

Giai đoạn một developer:

- Có thể self-review nhưng phải ghi rõ verification.
- Với security-sensitive change, nên tạo PR riêng để dễ audit.

Khi có thêm người:

- `main` nên bật branch protection.
- Yêu cầu PR review.
- Yêu cầu status checks pass.
- Chặn force push lên `main`.

## Release tag convention

Format:

```text
v<major>.<minor>.<patch>
```

Ví dụ:

```text
v0.1.0-docs-baseline
v0.2.0-codebase-foundation
v1.0.0-pilot
```\n