# GitHub workflow cho repo Camera-AI

Repo mục tiêu: https://github.com/HIepNgoc2006/Camera-AI

Folder này lưu toàn bộ quy tắc và template dùng để quản lý tiến độ, issue, commit, push, PR và MCP/GitHub CLI cho dự án AI Camera trường học.

## Mục tiêu

- Có một nguồn quy chuẩn rõ ràng trước khi đẩy code/docs lên GitHub.
- Giúp sếp theo dõi tiến độ qua GitHub Projects/Issues.
- Giúp agent có rule thống nhất khi tạo issue, commit, PR.
- Tránh rò rỉ dữ liệu nhạy cảm: `.env`, secret, camera credential, ảnh/video thật, face DB, dữ liệu học sinh.

## Danh sách file

| File | Mục đích |
|---|---|
| [commit-push-rules.md](commit-push-rules.md) | Quy tắc branch, commit, push, PR, merge |
| [project-board-rules.md](project-board-rules.md) | Cấu hình GitHub Project cho sếp theo dõi |
| [issue-labels-fields.md](issue-labels-fields.md) | Label, field, priority, status, milestone |
| [issue-templates.md](issue-templates.md) | Template issue cho Feature/Bug/Security/Docs/Ops/AI |
| [issues-backlog.md](issues-backlog.md) | Danh sách issue ban đầu nên tạo lên GitHub |
| [github-cli-and-mcp-guide.md](github-cli-and-mcp-guide.md) | Hướng dẫn dùng GitHub CLI và GitHub MCP an toàn |
| [create-github-issues.ps1](create-github-issues.ps1) | Script tạo labels, milestones và initial issues lên GitHub |
| [create-risk-issues.ps1](create-risk-issues.ps1) | Script tạo issue bổ sung cho rủi ro DDoS, vận hành, AI, privacy |

## Nguyên tắc dùng

1. Đọc `commit-push-rules.md` trước khi push.
2. Tạo Project theo `project-board-rules.md`.
3. Tạo labels/fields theo `issue-labels-fields.md`.
4. Tạo issue ban đầu dựa trên `issues-backlog.md`.
5. Chỉ dùng GitHub CLI/MCP với quyền tối thiểu.
6. Không đưa dữ liệu thật của học sinh/camera/secret lên GitHub.

## Khi nào cần xin quyền

Agent cần xin quyền trước khi:

- chạy `gh auth login`;
- tạo issue thật trên GitHub;
- push branch lên remote;
- tạo PR;
- sửa settings repo/project;
- thêm collaborator;
- bật GitHub Actions/Secrets;
- upload file lớn hoặc tài liệu có nguy cơ chứa dữ liệu nhạy cảm.

Nếu chỉ tạo/sửa file trong workspace này thì chưa cần quyền GitHub.
