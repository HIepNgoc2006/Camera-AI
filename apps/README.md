# Applications

Chứa các ứng dụng hướng người dùng được duyệt.

- `web-portal/`: Next.js skeleton cho Web Portal, được triển khai theo Issue #23.

- Gọi backend qua API Gateway và typed API client.
- Không kết nối trực tiếp database, queue, object storage hoặc internal service.
- Enforce route/UI guard, nhưng backend vẫn là nơi quyết định authorization cuối cùng.
- Không lưu dữ liệu nhạy cảm hoặc token trong local storage không an toàn.

Mobile vẫn được hoãn và chưa có application runtime.
