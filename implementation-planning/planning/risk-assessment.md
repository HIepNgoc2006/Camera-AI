# Risk assessment

## Kết luận

Hệ thống có thể triển khai cho trường học nếu thực hiện đúng security-first plan. Rủi ro lớn nhất không nằm ở việc dựng API hay app, mà nằm ở dữ liệu sinh trắc học, phân quyền sai, export dữ liệu, log/debug và vận hành ANSVIS/AI không có kiểm soát.

## Rủi ro dữ liệu

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| Lộ ảnh mặt học sinh qua log | Rất cao | Mask log, cấm log base64/face data, review logging |
| Lộ `.env`/secret | Rất cao | gitleaks, secret manager, `.gitignore`, rotation |
| Phụ huynh xem nhầm dữ liệu học sinh khác | Rất cao | Object-level authorization, permission matrix test |
| Export face DB/Event Log không kiểm soát | Rất cao | Ticket approval, audit, quyền ANSVIS tối thiểu |
| Link ảnh/video public | Rất cao | Private bucket, signed URL ngắn hạn |
| Dataset training bị copy ra ngoài | Rất cao | Encrypted storage, manifest, không dùng cloud cá nhân |
| Camera credential bị lộ | Cao | Secret reference, masking, không expose UI |

## Rủi ro AI

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| Nhận diện nhầm học sinh | Rất cao | Threshold test, shadow mode, human review |
| Báo vi phạm sai | Cao | Confidence threshold, reviewer, appeal flow |
| Hiểu nhầm model ANSVIS có sẵn đã đủ cho mọi nghiệp vụ | Cao | Tách rõ Facial Recognition có sẵn và 4 custom pipelines cần spec/shadow/acceptance riêng |
| Xả rác bị hiểu sai thành object detection đơn giản | Cao | Thiết kế Littering pipeline có tracking, ROI, left-object rule, human review |
| Hút thuốc false positive với bút/điện thoại/ăn uống | Cao | Kết quả là `nghi vấn`, cần review người quản lý và dữ liệu thực tế |
| Đồng phục/PPE thiếu định nghĩa class/rule cụ thể | Cao | Chốt quy định đồng phục/PPE trước khi cấu hình/train |
| Model drift do ánh sáng/góc camera | Cao | Theo dõi metric, retrain định kỳ |
| Training trên dữ liệu không có consent | Rất cao | Consent registry, dataset manifest |
| Dùng nhầm dataset ngoài không thuộc camera/ANSVIS dự án | Rất cao | Chỉ cho phép dataset từ camera dự án qua ANSVIS/AIBOX, dataset manifest bắt buộc, approval trước training |
| Model artifact bị thay đổi | Cao | Checksum, model registry, quyền storage |

## Rủi ro vận hành

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| ANSVIS task stop không ai biết | Cao | Health check, alert |
| GPU quá tải với 34 camera | Cao | Pilot, benchmark, Active Engine, task scheduling |
| License ANSVIS không đủ số AI task/camera | Cao | Xác minh license, max running tasks, kế hoạch task scheduling |
| Lệch giờ giữa camera/ANSVIS/backend/database | Cao | NTP/timezone chuẩn, kiểm tra timestamp trong E2E |
| Queue backlog | Cao | Queue monitoring, worker retry, DLQ |
| Queue retry không giới hạn gây nghẽn hệ thống | Cao | Retry limit, exponential backoff, DLQ, backpressure |
| Storage đầy | Cao | Disk alert, retention, lifecycle |
| Backup không restore được | Cao | Test restore định kỳ |
| Backup ANSVIS không bao gồm face DB/model/license | Cao | Backup riêng model/dataset/face DB nếu được phép, restore drill |
| Môi trường staging khác production quá nhiều | Cao | Staging-production parity checklist |
| Cấu hình sai môi trường hoặc dùng nhầm secret | Cao | Environment separation, config validation, secret manager |
| Observability không đủ để truy lỗi | Cao | Request ID, event ID, distributed tracing, dashboard, alert |
| Một developer khó bàn giao | Cao | README per service, runbook, coding rules |

## Rủi ro Web/Mobile/Notification

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| Push notification lộ thông tin nhạy cảm trên lock screen | Cao | Nội dung push tối giản, không gửi ảnh/tên vi phạm nhạy cảm |
| Notification gửi sai người | Rất cao | Recipient permission test, audit delivery, retry an toàn |
| Mobile device bị mất/cướp còn token đăng nhập | Cao | Secure storage, revoke token, logout all devices, refresh token rotation |
| Signed URL ảnh/video bị share ra ngoài | Cao | TTL ngắn, audit access, watermark/export policy |
| Report/export query quá nặng làm nghẽn DB | Trung bình/Cao | Pagination, async export, read model, rate limit |
| Export báo cáo quá rộng | Cao | Scope export theo quyền, audit, approval rule nếu nhạy cảm |

## Rủi ro maintainability

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| Microservices quá phức tạp | Trung bình | Monorepo, Docker Compose, chỉ tách domain rõ |
| Logic nằm trong endpoint | Cao | Application service + domain policy |
| Service đọc chéo database | Cao | API/event contract, schema ownership |
| Payload ANSVIS lan khắp codebase | Cao | ANSVIS Adapter + normalized event |
| Permission logic duplicate | Cao | Policy Pattern |
| Thiếu docs vận hành | Cao | Runbook và README bắt buộc |
| Vendor lock-in ANSCENTER/ANSVIS | Trung bình/Cao | Adapter layer, contract tests, capability matrix, version tracking |
| Test fixture/seed data dùng dữ liệu thật | Rất cao | Fake data only, fixture safety check, secret/data scan |

## Rủi ro AI và nghiệp vụ sau go-live

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| Model drift theo thời gian | Cao | Theo dõi false alert/missed detection, review định kỳ, retrain plan |
| False positive gây khiếu nại | Cao | Human review, appeal/manual correction workflow |
| Consent bị rút nhưng dữ liệu cũ vẫn còn | Rất cao | Consent withdrawal workflow, delete/anonymize job, audit |
| Retention job xóa nhầm dữ liệu cần đối soát | Cao | Dry-run, approval, backup trước job nguy hiểm, audit |
| Không có quy trình xử lý khi phụ huynh khiếu nại AI sai | Cao | Appeal workflow, evidence review, correction log |

## Rủi ro DDoS và abuse traffic

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| DDoS Web/API public | Cao | Cloudflare/WAF/CDN, API Gateway rate limit, monitoring |
| Brute force login/credential stuffing | Cao | Login throttling, MFA, lockout mềm, alert |
| Flood ANSVIS webhook bằng payload giả/lớn | Rất cao | IP allowlist, HMAC/token, body size limit, schema validation |
| Lạm dụng export/report để làm nghẽn hệ thống | Trung bình/Cao | Rate limit, async job, quota, monitoring |
| Public nhầm database/queue/object storage/ANSVIS | Rất cao | Private network, firewall, security group, port exposure scan |

## Điều kiện tối thiểu trước go-live

- Consent flow đã được duyệt.
- MFA cho Admin/BGH.
- RBAC/ABAC và object-level authorization đã test.
- ANSVIS HTTP Trigger có auth, payload tối thiểu.
- Debug mode production tắt.
- Object storage private, signed URL.
- Không có secret trong repo.
- Audit log cho thao tác nhạy cảm.
- Backup/restore đã test.
- Scan không còn Critical/High chưa xử lý.
- AI đã qua shadow mode.
- Có incident response runbook.
- Có DDoS/rate limit policy cho Web/API/webhook.
- Có NTP/timezone policy cho camera/ANSVIS/backend/database.
- Có notification privacy policy.
- Có signed URL TTL và evidence access audit.
- Có consent withdrawal/data deletion workflow.
