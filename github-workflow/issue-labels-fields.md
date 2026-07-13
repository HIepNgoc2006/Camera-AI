# GitHub issue labels and fields

## Labels bắt buộc

### Type labels

| Label | Mục đích |
|---|---|
| `type:feature` | Tính năng mới |
| `type:bug` | Bug |
| `type:security` | Bảo mật/privacy |
| `type:docs` | Tài liệu |
| `type:ops` | DevOps/vận hành |
| `type:ai` | AI/ANSVIS/model/event |
| `type:qa` | Test/UAT/acceptance |

### Priority labels

| Label | Khi dùng |
|---|---|
| `priority:critical` | Rò rỉ dữ liệu, sai phân quyền, hệ thống dừng |
| `priority:high` | Module chính, security gate, blocker |
| `priority:medium` | Việc quan trọng nhưng không chặn toàn hệ thống |
| `priority:low` | Cải tiến nhỏ |

### Area labels

| Label | Khu vực |
|---|---|
| `area:backend` | Backend/API/service |
| `area:web` | Web Portal |
| `area:mobile` | Mobile App |
| `area:database` | DB/schema/migration |
| `area:ansvis` | ANSVIS/AIBOX |
| `area:ai-model` | Model/dataset/training |
| `area:security` | Auth/RBAC/secret/audit/privacy |
| `area:devops` | Docker/CI/CD/deploy |
| `area:docs` | Tài liệu |
| `area:qa` | Test/UAT |

### Status helper labels

| Label | Khi dùng |
|---|---|
| `status:blocked` | Đang bị chặn |
| `status:needs-decision` | Cần sếp/khách hàng quyết định |
| `status:needs-info` | Thiếu thông tin |
| `status:ready` | Đủ thông tin để làm |

### Risk labels

| Label | Khi dùng |
|---|---|
| `risk:data-leak` | Có rủi ro rò rỉ dữ liệu |
| `risk:biometric` | Đụng dữ liệu khuôn mặt/sinh trắc |
| `risk:permission` | Đụng phân quyền |
| `risk:production` | Ảnh hưởng deploy/vận hành |
| `risk:customer-impact` | Ảnh hưởng khách hàng/nghiệm thu |

## Milestones đề xuất

| Milestone | Nội dung |
|---|---|
| `M1 - Docs Baseline` | Tài liệu, requirement, planning, GitHub workflow |
| `M2 - Codebase Foundation` | Repo structure, Docker, CI, env example |
| `M3 - Backend Core` | Auth, user, school, consent, audit |
| `M4 - AI/ANSVIS Integration` | Webhook, event ingestion, AI pipeline |
| `M5 - Web Portal` | Dashboard/admin/report |
| `M6 - Mobile App` | React Native app |
| `M7 - Integration & QA` | E2E, staging, performance |
| `M8 - Security Hardening` | Scan, backup, incident response |
| `M9 - UAT & Go-live` | Nghiệm thu, đào tạo, bàn giao |

## Issue ID convention

Issue title nên có prefix:

```text
[DOCS] ...
[OPS] ...
[BE] ...
[AI] ...
[WEB] ...
[MOB] ...
[SEC] ...
[QA] ...
[DBSEC] ...
```

Ví dụ:

```text
[SEC] Define secret management and .env policy
[AI] Implement ANSVIS webhook contract test
[BE] Create identity service skeleton
```
