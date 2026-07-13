# AI Camera School Project Workspace

> Baseline hiện hành: đọc `implementation-planning/planning/planning-index.md` và `workstream-implementation-plan.md`. Sáu chức năng đang triển khai là điểm danh học sinh, chấm công giáo viên, xả rác, nghi vấn hút thuốc, đồng phục học sinh và PPE bếp. Happiness index chỉ là Optional/Future Scope.

Workspace này chứa toàn bộ tài liệu, planning và asset tham chiếu cho dự án phần mềm AI Camera trường học.

## Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| [assets](assets) | Asset gốc, video, file media tham chiếu |
| [executive-summary](executive-summary) | Tài liệu tổng quan/kế hoạch gửi sếp hoặc khách hàng |
| [project-docs](project-docs) | Bộ tài liệu compact cho khách hàng/kỹ thuật: yêu cầu, flow, kiến trúc, API, AI, security, test, vận hành |
| [implementation-planning](implementation-planning) | Bộ planning triển khai: phase, gate, task, tracking, bug, security, MCP, codebase |
| [github-workflow](github-workflow) | Quy tắc GitHub: commit, push, PR, issues, project board, MCP/GitHub CLI |
| [references](references) | Tài liệu tham chiếu, tổng hợp video, nghiên cứu ANSCENTER |

## File nên đọc đầu tiên

| Mục đích | File |
|---|---|
| Xem tổng quan dự án | [executive-summary/Thiet-ke-tong-the-du-an-AI-Camera-Truong-hoc.md](executive-summary/Thiet-ke-tong-the-du-an-AI-Camera-Truong-hoc.md) |
| Xem kế hoạch backlog/task triển khai chi tiết | [executive-summary/Ke-hoach-backlog-task-trien-khai-chi-tiet-AI-Camera.md](executive-summary/Ke-hoach-backlog-task-trien-khai-chi-tiet-AI-Camera.md) |
| Xem bộ docs compact | [project-docs/docs-du-an-ai-camera/docs-index.md](project-docs/docs-du-an-ai-camera/docs-index.md) |
| Xem planning triển khai | [implementation-planning/planning/planning-index.md](implementation-planning/planning/planning-index.md) |
| Xem rule bắt buộc cho Agent trước khi code | [AGENTS.md](AGENTS.md) |
| Xem quy tắc GitHub/issue/commit/push | [github-workflow/README.md](github-workflow/README.md) |
| Xem tổng hợp video AIBOX/ANSVIS | [references/Tong-hop-video-TAP-HUAN-CAMERA-AIBOX.md](references/Tong-hop-video-TAP-HUAN-CAMERA-AIBOX.md) |

## Bộ planning compact nên đọc trước khi code

| Mục đích | File |
|---|---|
| Xem hướng triển khai đã tách Web/App, ANSVIS integration và AI training | [implementation-planning/planning/workstream-implementation-plan.md](implementation-planning/planning/workstream-implementation-plan.md) |
| Master plan | [implementation-planning/planning/system-master-plan.md](implementation-planning/planning/system-master-plan.md) |
| Model ANSVIS đã có/chưa có | [implementation-planning/planning/ansvis-model-capability-matrix.md](implementation-planning/planning/ansvis-model-capability-matrix.md) |
| Kiến trúc, database, tools, libraries | [implementation-planning/planning/architecture-stack.md](implementation-planning/planning/architecture-stack.md) |
| PostgreSQL, mã hóa dữ liệu, backup, retention | [implementation-planning/planning/database-and-encryption-plan.md](implementation-planning/planning/database-and-encryption-plan.md) |
| Checklist công cụ, thư viện, phần mềm cần chuẩn bị | [implementation-planning/planning/tooling-requirements.md](implementation-planning/planning/tooling-requirements.md) |
| Security, privacy, `.env`, secret | [implementation-planning/planning/security-privacy-plan.md](implementation-planning/planning/security-privacy-plan.md) |
| AI, ANSVIS, ANSTS, data safety | [implementation-planning/planning/ai-ansvis-plan.md](implementation-planning/planning/ai-ansvis-plan.md) |
| Coding rules, agent rules, design patterns | [AGENTS.md](AGENTS.md) và [implementation-planning/planning/coding-agent-rules.md](implementation-planning/planning/coding-agent-rules.md) |
| QA, test, acceptance | [implementation-planning/planning/delivery-quality-plan.md](implementation-planning/planning/delivery-quality-plan.md) |
| Tracking, bug, release, operations | [implementation-planning/planning/operations-tracking-plan.md](implementation-planning/planning/operations-tracking-plan.md) |
| Risk assessment | [implementation-planning/planning/risk-assessment.md](implementation-planning/planning/risk-assessment.md) |

## Quy tắc quản lý

- Tài liệu gửi lãnh đạo/khách hàng để trong `executive-summary`.
- Tài liệu đặc tả hệ thống để trong `project-docs`.
- Kế hoạch triển khai/coding/task tracking để trong `implementation-planning`.
- File nguồn/video/reference để trong `assets` hoặc `references`.
- Không để file rời ở root trừ `README.md` và file cấu hình dự án sau này.
