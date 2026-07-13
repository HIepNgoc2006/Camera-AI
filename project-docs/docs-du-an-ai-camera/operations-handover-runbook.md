# Operations, handover and runbook

## Mục tiêu

Tài liệu này mô tả cách đào tạo, bàn giao, vận hành và hỗ trợ hệ thống sau khi triển khai. Nội dung dành cho đội vận hành, admin trường và bên phát triển phần mềm.

## Đào tạo người dùng

| Nhóm | Nội dung đào tạo |
|---|---|
| Admin hệ thống | Quản lý tài khoản, phân quyền, cấu hình, audit |
| BGH | Dashboard, báo cáo, xử lý sự kiện quan trọng |
| Giáo viên | Xem lớp/học sinh được phân công, điểm danh, thông báo |
| Phụ huynh | Mobile App, điểm danh con, thông báo |
| Nhân sự vận hành | Trạng thái camera/ANSVIS, monitoring, backup, sự cố |

## Bàn giao

| Hạng mục | Nội dung |
|---|---|
| Tài khoản | Tài khoản cá nhân, không dùng chung admin |
| Tài liệu | User guide, admin guide, runbook, API/architecture summary |
| Cấu hình | Env/config đã masking, danh sách service, endpoint |
| Backup | Chính sách backup, restore test evidence |
| Monitoring | Dashboard, alert, người nhận cảnh báo |
| Security | Quy trình cấp quyền, revoke, incident response |
| Hỗ trợ | Kênh hỗ trợ, SLA, quy trình tạo ticket |

## Runbook kiểm tra hệ thống

| Kiểm tra | Cách xử lý nếu lỗi |
|---|---|
| Web/Mobile truy cập được | Kiểm tra API Gateway, frontend deploy, DNS/TLS |
| API health | Kiểm service, log, database connection |
| Queue backlog | Kiểm worker, RabbitMQ, DLQ |
| ANSVIS task status | Kiểm ANSVIS dashboard, task start/stop, license |
| Event ingestion | Gửi test trigger, kiểm request ID/event ID |
| Storage usage | Kiểm bucket/disk, lifecycle, retention |
| Notification | Kiểm queue, provider, delivery log |
| Backup | Kiểm job backup và restore test định kỳ |

## Backup/restore

Backup cần bao gồm:

- PostgreSQL.
- Object storage evidence.
- Model artifact.
- Dataset manifest.
- ANSVIS config/restore point.
- Face DB nếu được phép và có quy trình bảo mật riêng.

Lưu ý: theo tài liệu ANSVIS, restore point có thể không bao gồm đầy đủ uploaded files, user model, face DB và license DB. Vì vậy cần backup riêng các phần quan trọng ngoài restore point.

## Support/SLA đề xuất

| Mức | Ví dụ | Phản hồi |
|---|---|---|
| Critical | Rò rỉ dữ liệu, sai phân quyền, hệ thống dừng | Ngay khi nhận |
| High | Mất event, không điểm danh được, notification sai người | Trong ngày |
| Medium | Report sai, UI lỗi flow phụ | Theo lịch xử lý |
| Low | Cải tiến nhỏ, wording, cosmetic | Gom theo release |

## Quy trình xử lý sự cố

1. Nhận ticket/sự cố.
2. Phân loại mức độ.
3. Thu thập request ID/event ID/log đã masking.
4. Cô lập lỗi nếu liên quan bảo mật.
5. Khắc phục hoặc rollback.
6. Xác nhận lại với người báo lỗi.
7. Ghi root cause và biện pháp phòng ngừa.

## Quy trình thay đổi/release

- Mọi thay đổi production cần release note.
- Thay đổi database cần migration và backup trước release.
- Thay đổi AI model/threshold/ROI cần ghi version và rollback.
- Thay đổi phân quyền/consent cần security review.
- Release phải có kế hoạch rollback.

## Vận hành định kỳ

| Tần suất | Việc cần làm |
|---|---|
| Hằng ngày | Kiểm health, queue, ANSVIS task, storage, alert |
| Hằng tuần | Review bug/security ticket, kiểm backup |
| Hằng tháng | Access review, dependency/security scan, test restore |
| Theo học kỳ | Review consent, retention, model accuracy, camera mapping |\n