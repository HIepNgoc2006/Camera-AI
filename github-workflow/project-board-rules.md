# GitHub Project board rules

## Project đề xuất

Tên project:

```text
AI Camera School - Delivery Board
```

Mục tiêu:

- Sếp xem được tiến độ tổng quan.
- Dev/agent quản lý task chi tiết.
- Bug/security/AI issue không bị lẫn với task thường.
- Có trạng thái blocker và rủi ro rõ ràng.

## Views cần tạo

| View | Kiểu | Mục đích |
|---|---|---|
| Executive Overview | Table | View gọn cho sếp |
| Phase Board | Board | Theo dõi theo phase/status |
| Security & Risk | Table | Các issue bảo mật/rủi ro |
| Bug Tracking | Board | Bug theo severity/status |
| AI/ANSVIS Integration | Table | Các issue AI, ANSVIS, AIBOX |
| UAT & Acceptance | Table | Nghiệm thu, test, bàn giao |
| Weekly Report | Table | Việc xong/đang làm/blocker trong tuần |

## Fields cần có

| Field | Type | Giá trị |
|---|---|---|
| `Status` | Single select | Backlog, Ready, In Progress, Review, Blocked, Done |
| `Phase` | Single select | Docs, Foundation, Backend, AI/ANSVIS, Web, Mobile, Integration, Security, UAT, Operations |
| `Type` | Single select | Feature, Bug, Security, Docs, Ops, AI, QA |
| `Priority` | Single select | Critical, High, Medium, Low |
| `Risk Level` | Single select | Critical, High, Medium, Low |
| `Target Date` | Date | Ngày mục tiêu nếu có |
| `Progress` | Number | 0-100 |
| `Blocked Reason` | Text | Lý do bị block |
| `Evidence` | Text | Link test/log/screenshot/docs |

## Executive Overview filter

Chỉ hiển thị:

- `Priority = Critical OR High`
- hoặc `Risk Level = Critical OR High`
- hoặc `Status = Blocked`
- hoặc các issue milestone chính.

Ẩn bớt task kỹ thuật nhỏ để sếp không bị rối.

## Weekly status update format

Mỗi tuần cập nhật Project status:

```markdown
## Weekly status - YYYY-MM-DD

### Done
- ...

### In progress
- ...

### Blocked / Risk
- ...

### Next
- ...

### Decision needed
- ...
```

## Rule cho issue status

| Status | Ý nghĩa |
|---|---|
| Backlog | Chưa làm |
| Ready | Đã đủ thông tin, có thể làm |
| In Progress | Đang làm |
| Review | Đang tự review/test/chờ xác nhận |
| Blocked | Bị chặn vì thiếu thông tin/quyền/quyết định |
| Done | Đạt Definition of Done |

Không set `Done` nếu chưa có evidence.

Vì dự án có một developer chính, giới hạn WIP triển khai là một issue ở trạng thái `In Progress`. Chỉ mở thêm issue song song cho thao tác chờ ngoài hệ thống hoặc kiểm tra đọc-only không làm gián đoạn issue chính. Issue Critical/High không được chuyển sang `In Progress` nếu thiếu `Blocked by`, acceptance criteria hoặc security/privacy impact tương ứng.
