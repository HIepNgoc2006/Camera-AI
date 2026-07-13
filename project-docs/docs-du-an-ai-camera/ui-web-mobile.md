# UI sitemap and Web/Mobile screens

## Mục tiêu UI

UI cần đơn giản, dễ dùng cho phụ huynh, giáo viên và ban giám hiệu. Màn hình phải hiển thị đúng quyền; người dùng không được thấy dữ liệu ngoài phạm vi của mình.

## Web Portal sitemap

| Nhóm màn hình | Người dùng | Chức năng |
|---|---|---|
| Login/MFA | Tất cả | Đăng nhập, xác thực bảo mật |
| Dashboard BGH | BGH/Admin | Tổng quan điểm danh, vi phạm, camera, cảnh báo |
| Quản lý học sinh/lớp | Admin/BGH/Giáo viên theo quyền | Danh sách học sinh, lớp, phụ huynh, phân công |
| Điểm danh | BGH/Giáo viên/Admin | Trạng thái điểm danh theo lớp/ngày |
| Chấm công | BGH/Admin/Nhân sự | Dữ liệu chấm công cán bộ/giáo viên |
| Vi phạm | BGH/Giáo viên/Admin | Danh sách sự kiện, review, xử lý |
| Camera/AI Task | Admin/Vận hành | Metadata camera, trạng thái integration |
| Consent | Admin/BGH | Trạng thái đồng ý xử lý dữ liệu |
| Báo cáo | BGH/Admin | Thống kê/export có audit |
| Audit/Security | Admin/Auditor | Lịch sử truy cập, export, thay đổi quyền |
| Cấu hình | Admin | Role, permission, notification policy |

## Mobile App sitemap

| Nhóm màn hình | Người dùng | Chức năng |
|---|---|---|
| Login | Phụ huynh/Giáo viên/BGH | Đăng nhập, refresh token, logout |
| Home | Theo vai trò | Tóm tắt thông tin chính |
| Con của tôi | Phụ huynh | Điểm danh, thông báo, sự kiện được phép xem |
| Lớp của tôi | Giáo viên | Điểm danh/lịch sử học sinh được phân công |
| Notification | Tất cả | Thông báo theo quyền |
| Event detail | Theo quyền | Chi tiết sự kiện, evidence nếu được phép |
| Report quick view | BGH | Thống kê nhanh |
| Profile/Security | Tất cả | Thông tin tài khoản, đổi mật khẩu, logout |

## Wireframe mức chức năng

### Dashboard BGH

```text
+---------------------------------------------------+
| Header: School / Date / User / Alert              |
+----------------------+----------------------------+
| Attendance summary   | Violation summary          |
| Present/Late/Absent  | Smoking/Trash/Uniform      |
+----------------------+----------------------------+
| Camera/ANSVIS status | Event trend chart          |
+----------------------+----------------------------+
| Recent events with review status                  |
+---------------------------------------------------+
```

### Phụ huynh mobile

```text
+-----------------------------+
| Home                        |
| Child attendance today      |
| Latest notifications        |
| Allowed event details       |
| Profile / Security          |
+-----------------------------+
```

### Review vi phạm

```text
+---------------------------------------------------+
| Filter: date / camera / type / status             |
+---------------------------------------------------+
| Event list                                        |
+---------------------------------------------------+
| Event detail: metadata, evidence, confidence      |
| Actions: approve / reject / request review        |
+---------------------------------------------------+
```

## Quy tắc UX/security

- Không hiển thị ảnh/video nếu user không có quyền.
- Push notification không chứa ảnh mặt hoặc dữ liệu nhạy cảm.
- Màn hình export phải hiện cảnh báo và ghi audit.
- Route guard bắt buộc cho Web.
- Secure storage cho Mobile token.
- UI ẩn action không được phép, nhưng backend vẫn phải enforce quyền.
- Mọi bảng dữ liệu nhạy cảm cần filter, paging, tránh tải quá nhiều.

## Trạng thái cần hiển thị rõ

| Trạng thái | Ví dụ |
|---|---|
| Chờ xử lý | Event vi phạm cần review |
| Đã xác nhận | Điểm danh/chấm công/vi phạm đã duyệt |
| Bị từ chối | Event AI sai hoặc thiếu bằng chứng |
| Thiếu consent | Không xử lý biometric |
| Camera/ANSVIS lỗi | Task stop, event delay, mất kết nối |
| Đang đồng bộ | Event/notification/report đang xử lý |

## Tiêu chí nghiệm thu UI

- Người dùng chỉ thấy dữ liệu đúng quyền.
- Flow chính thao tác trong số bước hợp lý.
- Mobile dùng được cho phụ huynh/giáo viên với thông tin cần thiết.
- Dashboard BGH đủ tổng quan và có drill-down.
- Có trạng thái loading/error/empty.
- Evidence nhạy cảm được bảo vệ.\n