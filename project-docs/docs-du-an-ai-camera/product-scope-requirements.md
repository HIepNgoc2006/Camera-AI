# Product scope and requirements

## Tổng quan hệ thống

Hệ thống AI Camera cho trường học gồm 34 camera AI, ANSVIS/AIBOX hoặc nền tảng AI tương đương, Backend xử lý dữ liệu, Web Portal và Mobile App React Native. Camera được đặt tại cổng trường, sân trường, hành lang và khu bếp ăn; không lắp trong lớp học.

Mục tiêu baseline là tự động hóa điểm danh, chấm công, phát hiện các hành vi/vi phạm đã chốt và cung cấp thông tin kịp thời cho nhà trường/phụ huynh theo đúng quyền truy cập. Happiness index không thuộc baseline hiện tại; nếu phát sinh phải đi qua change request và đánh giá riêng tư riêng.

## Cấu hình camera nghiệp vụ

| Nhóm camera | Số lượng | Mục đích |
|---|---:|---|
| Điểm danh/chấm công/đồng phục | 16 | Điểm danh học sinh, nhận diện vào/ra, chấm công giáo viên và hỗ trợ Student Uniform theo mapping phần mềm được khóa |
| Xả rác | 8 | Phát hiện hành vi xả rác ở sân/hành lang/khu vực chung |
| Hút thuốc | 8 | Phát hiện hành vi hút thuốc trong khuôn viên |
| Bếp ăn/bảo hộ | 2 | Giám sát đồng phục/bảo hộ khu bếp ăn |

## Vai trò người dùng

| Vai trò | Quyền chính |
|---|---|
| Admin hệ thống | Quản lý tài khoản, phân quyền, cấu hình hệ thống, audit |
| Ban giám hiệu | Xem dashboard toàn trường, báo cáo, sự kiện quan trọng |
| Giáo viên | Xem học sinh/lớp được phân công, điểm danh, thông báo liên quan |
| Phụ huynh | Xem thông tin con mình, điểm danh, thông báo được phép |
| Nhân sự/Quản lý bếp | Xem sự kiện liên quan bảo hộ/bếp ăn theo quyền |
| Nhân sự vận hành | Theo dõi trạng thái hệ thống, camera, job, backup |
| Auditor | Xem log/audit theo phạm vi được cấp |

## Chức năng chính

| Module | Chức năng |
|---|---|
| Xác thực & phân quyền | Login/logout, MFA cho tài khoản quan trọng, RBAC/ABAC, session/token |
| Hồ sơ trường học | Học sinh, phụ huynh, giáo viên, lớp, phân công |
| Consent | Quản lý đồng ý xử lý dữ liệu sinh trắc học/trẻ em |
| Camera registry | Quản lý metadata camera, khu vực, trạng thái, mapping ANSVIS |
| AI event ingestion | Nhận event từ ANSVIS/AIBOX, validate, chống trùng, đưa vào xử lý |
| Điểm danh | Ghi nhận vào/ra, trạng thái điểm danh, đối soát |
| Chấm công | Ghi nhận cán bộ/giáo viên vào/ra, báo cáo công |
| Vi phạm | Đồng phục, đi trễ, xả rác, hút thuốc, thiếu bảo hộ bếp |
| Notification | Thông báo in-app/push/email theo quyền và chính sách |
| Dashboard/report | Thống kê theo ngày/lớp/khu vực/sự kiện, export có kiểm soát |
| Audit/security | Ghi nhận thao tác nhạy cảm, theo dõi truy cập/export |
| Operations | Monitoring, backup, restore, incident handling |

## Yêu cầu phi chức năng

| Nhóm | Yêu cầu |
|---|---|
| Bảo mật | TLS, secret manager, RBAC/ABAC, object-level authorization, audit log |
| Riêng tư | Consent, data minimization, retention, hạn chế export |
| Hiệu năng | Xử lý event gần real-time, queue/worker cho tải cao |
| Khả dụng | Có monitoring, alert, backup, rollback |
| Dễ bảo trì | Code tách module/service, tài liệu rõ, migration, test |
| Mở rộng | Có thể tăng camera, tăng worker, tách service nóng |

## Ngoài phạm vi

- Không thi công phần cứng.
- Không chịu trách nhiệm chất lượng camera/đường truyền vật lý nếu chưa được bàn giao chuẩn.
- Không xử lý dữ liệu sinh trắc học nếu thiếu consent hoặc chính sách pháp lý cần thiết.
- Không dùng AI tự động đưa ra quyết định kỷ luật nghiêm trọng nếu chưa có human review.

## Điều kiện nghiệm thu cấp yêu cầu

- Khách hàng xác nhận danh sách vai trò và quyền.
- Khách hàng xác nhận danh sách camera/khu vực sử dụng phần mềm.
- Khách hàng xác nhận quy trình consent và phạm vi thông báo.
- Các module chính có tiêu chí test/UAT rõ.
- Các chức năng liên quan dữ liệu trẻ em có phân quyền và audit.
