# GitHub CLI and MCP guide

## Repo mục tiêu

```text
https://github.com/HIepNgoc2006/Camera-AI
```

## Khi nào dùng GitHub CLI

Dùng `gh` khi cần:

- kiểm tra repo remote;
- tạo issue;
- tạo labels/milestones;
- tạo PR;
- xem PR/issue status;
- sync project/task nếu cần.

Không dùng `gh` để upload secret, `.env`, dữ liệu thật, video camera, face DB, dataset.

## Kiểm tra GitHub CLI

```powershell
gh --version
gh auth status
```

Nếu chưa login:

```powershell
gh auth login
```

Agent phải xin quyền người dùng trước khi chạy login hoặc thao tác GitHub thật.

## Kết nối local folder với repo

Chỉ thực hiện nếu workspace này cần trở thành working tree của repo:

```powershell
git init
git remote add origin https://github.com/HIepNgoc2006/Camera-AI.git
git branch -M main
git status
```

Nếu repo remote đã có file, cần pull trước và xử lý conflict cẩn thận:

```powershell
git pull origin main --allow-unrelated-histories
```

Không force push nếu chưa được user xác nhận.

## Push lần đầu

Trước khi push:

```powershell
git status
git diff --stat
```

Kiểm tra không có secret:

```powershell
rg -n "\.env|BEGIN PRIVATE KEY|password=|token=|rtsp://|secret|license" .
```

Sau đó:

```powershell
git add .
git commit -m "docs(github): add workflow rules and issue backlog"
git push -u origin main
```

Agent phải xin quyền trước khi chạy `git push`.

## Tạo label bằng GitHub CLI

Ví dụ:

```powershell
gh label create "type:feature" --repo HIepNgoc2006/Camera-AI --color "1D76DB" --description "Feature work"
gh label create "type:bug" --repo HIepNgoc2006/Camera-AI --color "D73A4A" --description "Bug"
gh label create "type:security" --repo HIepNgoc2006/Camera-AI --color "B60205" --description "Security or privacy issue"
gh label create "priority:critical" --repo HIepNgoc2006/Camera-AI --color "B60205" --description "Critical priority"
gh label create "area:ansvis" --repo HIepNgoc2006/Camera-AI --color "5319E7" --description "ANSVIS/AIBOX integration"
```

## Tạo issue bằng GitHub CLI

Ví dụ:

```powershell
gh issue create `
  --repo HIepNgoc2006/Camera-AI `
  --title "[SEC] Define secret management and .env policy" `
  --body "Define and enforce secret management rules based on AGENTS.md and github-workflow/commit-push-rules.md." `
  --label "type:security,area:security,priority:critical,risk:data-leak"
```

## GitHub MCP

Khuyến nghị dùng GitHub MCP Server chính thức, không dùng MCP cộng đồng cho repo này nếu chưa audit.

Mục tiêu dùng MCP:

- đọc issues;
- tạo/update issues;
- đọc PR;
- tóm tắt tiến độ;
- hỗ trợ review task;
- không đọc secret hoặc file nhạy cảm.

Quy tắc MCP:

- Cấp token quyền tối thiểu.
- Không cấp quyền admin repo nếu chỉ cần tạo issue.
- Không cho MCP đọc `.env` hoặc secret.
- Không dùng MCP để upload dữ liệu thật của học sinh/camera.
- Mọi hành động ghi lên GitHub phải được user cho phép nếu agent chưa được giao rõ.

## Token permission gợi ý

Nếu dùng PAT, chỉ cấp quyền đúng nhu cầu:

| Nhu cầu | Quyền |
|---|---|
| Đọc repo public | Không cần token hoặc read-only |
| Tạo issue | Issues read/write |
| Tạo PR/push branch | Contents read/write, Pull requests read/write |
| Quản lý labels/milestones | Issues write hoặc repo-level phù hợp |
| Quản lý repo settings/secrets | Chỉ cấp khi thực sự cần |

Không dùng token cá nhân quá rộng cho agent.\n