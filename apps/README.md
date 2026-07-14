# Applications

Chứa các ứng dụng hướng người dùng được duyệt, bắt đầu với Web Portal khi milestone Web được kích hoạt.

- Gọi backend qua API Gateway và typed API client.
- Không kết nối trực tiếp database, queue, object storage hoặc internal service.
- Enforce route/UI guard, nhưng backend vẫn là nơi quyết định authorization cuối cùng.
- Không lưu dữ liệu nhạy cảm hoặc token trong local storage không an toàn.

Không có application runtime nào được tạo trong issue scaffold này.
