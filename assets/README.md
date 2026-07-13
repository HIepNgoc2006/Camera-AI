# Asset policy

Thư mục này chỉ dùng làm vị trí quy ước cho tài liệu tham chiếu cục bộ. Media camera, video đào tạo dung lượng lớn, dataset, face image, evidence và model artifact không được commit trực tiếp vào Git.

Quy tắc:

- `assets/videos/` bị ignore mặc định.
- Chỉ dùng Git LFS hoặc kho lưu trữ riêng sau khi có phê duyệt, data classification, quyền truy cập và retention phù hợp.
- Không lưu ảnh/video thật của học sinh, face DB, raw ANSVIS payload, RTSP credential hoặc dữ liệu camera dự án trong repository.
- Tài liệu Markdown có thể trỏ đến tên/nguồn asset đã được phê duyệt nhưng không được chứa signed URL, secret hoặc đường dẫn production riêng tư.
