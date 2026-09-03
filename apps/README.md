# Applications

Chứa các ứng dụng hướng người dùng được duyệt.

- `web-portal/`: Next.js App Router baseline có same-origin BFF cho challenge/login/session refresh,
  logout/logout-all, route guard mặc định từ chối và trang `/app/attendance` được bảo vệ. Provider
  session/attendance mặc định vẫn inactive để không biến fixture hoặc contract thành dữ liệu live.

- Gọi backend qua API Gateway và typed API client.
- Không kết nối trực tiếp database, queue, object storage hoặc internal service.
- Enforce route/UI guard, nhưng backend vẫn là nơi quyết định authorization cuối cùng.
- Không lưu dữ liệu nhạy cảm hoặc token trong local storage không an toàn.

Các dashboard/màn hình nghiệp vụ khác chưa được triển khai. Mobile vẫn được hoãn và chưa có
application runtime. Trạng thái mã nguồn trên không đồng nghĩa Web Portal đã được deploy hoặc nối
production provider.
