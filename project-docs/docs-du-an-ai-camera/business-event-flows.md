# Business flow, event flow and sequence

## Mục tiêu

Tài liệu này mô tả các luồng nghiệp vụ chính từ camera/ANSVIS đến Backend, Web Portal, Mobile App và Notification. Mục tiêu là giúp khách hàng hiểu dữ liệu đi như thế nào và hệ thống phản ứng ra sao.

## Luồng tổng thể

```text
Camera RTSP/ONVIF
  -> ANSVIS/AIBOX AI Task
  -> Event Log / HTTP Trigger
  -> Backend API Gateway
  -> ANSVIS Adapter
  -> Event Ingestion
  -> Queue/Worker
  -> Attendance / Timekeeping / Violation
  -> Notification / Dashboard / Report
```

## Quy trình điểm danh học sinh

| Bước | Mô tả | Kiểm soát |
|---|---|---|
| 1 | Học sinh đi qua khu vực camera điểm danh | Camera đặt ngoài lớp học |
| 2 | ANSVIS/AIBOX nhận diện/tạo event | Theo task, threshold, ROI đã cấu hình |
| 3 | Backend nhận event | Validate nguồn, payload, chống trùng |
| 4 | Hệ thống kiểm tra consent và mapping học sinh | Thiếu consent thì không xử lý biometric |
| 5 | Ghi nhận điểm danh | Có audit và trạng thái |
| 6 | Gửi thông báo nếu chính sách cho phép | Chỉ gửi đúng phụ huynh/giáo viên liên quan |
| 7 | Hiển thị dashboard/report | Theo phân quyền |

## Quy trình chấm công cán bộ/giáo viên

| Bước | Mô tả |
|---|---|
| 1 | Cán bộ/giáo viên đi qua khu vực camera được cấu hình |
| 2 | ANSVIS tạo event nhận diện/chấm công |
| 3 | Backend chuẩn hóa event và kiểm tra người dùng |
| 4 | Hệ thống ghi nhận vào/ra theo ca hoặc thời gian |
| 5 | Người có quyền xem báo cáo chấm công |

## Quy trình phát hiện vi phạm

| Loại vi phạm | Luồng xử lý |
|---|---|
| Đi trễ | Event đến sau khung giờ quy định, hệ thống tạo trạng thái đi trễ |
| Đồng phục | AI phát hiện không đúng đồng phục/quy định, đưa vào review nếu cần |
| Xả rác | Event hành vi xả rác, lưu evidence, thông báo theo chính sách |
| Hút thuốc | Event hút thuốc, ưu tiên cảnh báo BGH/nhân sự phụ trách |
| Thiếu bảo hộ bếp | Event thiếu mũ/khẩu trang/tạp dề nếu được cấu hình |

Nguyên tắc: sự kiện nhạy cảm hoặc độ tin cậy thấp cần human review trước khi dùng làm kết luận chính thức.

## Event flow chi tiết

| Thành phần | Trách nhiệm |
|---|---|
| Camera | Cung cấp luồng RTSP/ONVIF |
| ANSVIS/AIBOX | Chạy AI Task, ROI, threshold, trigger |
| HTTP Trigger | Gửi event sang Backend |
| API Gateway | TLS, route, rate limit, request ID |
| ANSVIS Adapter | Validate auth/schema, normalize payload |
| Event Ingestion | Chống trùng, lưu metadata, đưa queue |
| Worker | Xử lý nghiệp vụ bất đồng bộ |
| Business Services | Attendance, timekeeping, violation |
| Notification | Gửi thông báo đúng người |
| Web/Mobile | Hiển thị theo quyền |

## Sequence: event điểm danh

```text
ANSVIS -> Backend: POST attendance event
Backend -> Backend: validate token/schema/idempotency
Backend -> Consent Service: check biometric consent
Backend -> Attendance Service: create/update attendance
Backend -> Audit Log: record sensitive action
Backend -> Notification Service: enqueue notification
User -> Web/Mobile: view attendance by permission
```

## Sequence: người dùng xem sự kiện

```text
User -> Web/Mobile: request event detail
Web/Mobile -> API Gateway: authorized request
API Gateway -> Service: check role and object-level permission
Service -> Evidence Storage: generate signed URL if allowed
Service -> Audit Log: record view/export if sensitive
Service -> User: return allowed fields only
```

## Nguyên tắc xử lý lỗi

| Tình huống | Cách xử lý |
|---|---|
| Event trùng | Bỏ qua hoặc merge theo idempotency key |
| Payload không hợp lệ | Reject, ghi log đã masking, đưa vào dead-letter nếu cần |
| Thiếu consent | Không xử lý biometric, ghi trạng thái bị chặn |
| Notification lỗi | Retry theo queue, không làm mất bản ghi nghiệp vụ |
| ANSVIS tạm dừng | Alert vận hành, không tự sửa dữ liệu lịch sử |\n