# Bộ tài liệu dự án AI Camera trường học

## Mục tiêu

Bộ tài liệu này mô tả hệ thống AI Camera tích hợp Web Portal, Mobile App, Backend và ANSVIS/AIBOX cho trường học. Tài liệu được viết theo hướng dễ đọc cho khách hàng, ban giám hiệu và người quản lý dự án, đồng thời vẫn đủ thông tin để đội kỹ thuật triển khai.

## Phạm vi quan trọng

Team phần mềm phụ trách:

- Backend/API.
- AI integration với ANSVIS/AIBOX.
- Web Portal.
- Mobile App React Native.
- Database.
- Bảo mật, phân quyền, audit, consent.
- Monitoring, backup, vận hành phần mềm.

Team phần mềm không phụ trách:

- Khảo sát hiện trường.
- Mua camera/phần cứng.
- Lắp đặt camera.
- Đi dây mạng vật lý.
- Thi công hạ tầng mạng tại trường.

Điều kiện tích hợp: bên thi công/khách hàng bàn giao luồng camera RTSP/ONVIF hoặc cấu hình ANSVIS/API cần thiết.

## Danh sách tài liệu compact

| File | Nội dung |
|---|---|
| [product-scope-requirements.md](product-scope-requirements.md) | SRS, vai trò người dùng, chức năng chính, phạm vi |
| [business-event-flows.md](business-event-flows.md) | Quy trình nghiệp vụ, event flow, sequence flow |
| [technical-architecture-data-api.md](technical-architecture-data-api.md) | Kiến trúc, database/ERD, API, deployment, infra |
| [ui-web-mobile.md](ui-web-mobile.md) | Sitemap, màn hình Web/Mobile, wireframe mức chức năng |
| [ai-ansvis-security-privacy.md](ai-ansvis-security-privacy.md) | AI/ANSVIS/AIBOX, Facial Recognition, custom pipelines, security, privacy, consent |
| [testing-acceptance-risk.md](testing-acceptance-risk.md) | Test plan, acceptance criteria, risk register |
| [operations-handover-runbook.md](operations-handover-runbook.md) | Đào tạo, bàn giao, vận hành, backup, support |

## Cách đọc đề xuất

- Ban giám hiệu/khách hàng: đọc `product-scope-requirements`, `ui-web-mobile`, `testing-acceptance-risk`.
- Đội kỹ thuật: đọc toàn bộ, đặc biệt `technical-architecture-data-api` và `ai-ansvis-security-privacy`.
- Người vận hành sau go-live: đọc `operations-handover-runbook`.
- Agent/developer khi code: đọc thêm `../../implementation-planning/planning/planning-index.md` và root `../../AGENTS.md`.
- Nếu task liên quan database, mã hóa, backup hoặc retention: đọc thêm `../../implementation-planning/planning/database-and-encryption-plan.md`.

## Nguyên tắc bảo mật xuyên suốt

Hệ thống xử lý dữ liệu trẻ em, khuôn mặt, điểm danh, chấm công và ảnh/video sự kiện. Vì vậy:

- Bảo mật là điều kiện bắt buộc ở mọi phase.
- Dữ liệu sinh trắc học chỉ xử lý khi có consent hợp lệ.
- Phân quyền phải kiểm soát theo vai trò và phạm vi dữ liệu.
- Mọi thao tác xem/sửa/xóa/export dữ liệu nhạy cảm phải có audit log.
- Không lưu secret, ảnh mặt, video thật, face DB hoặc dữ liệu học sinh thật vào Git.
