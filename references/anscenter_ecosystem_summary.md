# Tài liệu tóm tắt chuyên sâu Hệ sinh thái ANSCENTER

Tài liệu này cung cấp chi tiết kỹ thuật, các tham số cấu hình và cơ chế tích hợp của các sản phẩm thuộc hệ sinh thái ANSCENTER.

---

## 1. Chi tiết các công cụ Triển khai (Deployment Tools)

### A. ANSVIS (Hệ thống phân tích video Edge AI 24/7)
ANSVIS là trung tâm xử lý dữ liệu camera trực tiếp. Cơ chế hoạt động chi tiết gồm:

1. **Nguồn Camera đầu vào (Camera Sources)**:
   * **Simulated Camera (Giả lập)**: Cho phép nạp đường dẫn tệp video hoặc ảnh tĩnh từ máy tính để kiểm thử luồng xử lý offline.
   * **RTSP Stream (Luồng mạng)**: Hỗ trợ chuẩn ONVIF tự động dò tìm camera trong mạng nội bộ. Yêu cầu cấu hình:
     * Địa chỉ IP/Host và Cổng RTSP (mặc định 554).
     * Đường dẫn luồng (Stream path - ví dụ `/h264`).
     * Tài khoản đăng nhập (Username/Password) hoặc payload đăng nhập tùy chỉnh (Custom Login Payload) cho các thiết bị chuyên dụng.
   * **Webcam**: Nhận diện trực tiếp qua driver DirectShow của hệ điều hành dành cho camera USB.

2. **Cấu hình Tác vụ AI & Thiết lập Luật (AI Task Rules)**:
   * **Quy tắc Vùng (ROI)**: Định nghĩa vùng đa giác (Polygon) để phát hiện vật thể xâm nhập hoặc vẽ đường thẳng (Line crossing) để đếm số lượng vật thể đi qua theo hướng xác định.
   * **Bộ lọc giảm báo động giả**:
     * `Model Score Threshold`: Ngưỡng điểm tin cậy tối thiểu của AI (ví dụ > 0.5) để kích hoạt sự kiện.
     * `Min Object Size`: Loại bỏ các vật thể có kích thước quá nhỏ (nhiễu, động vật nhỏ).
     * `Presence Time`: Thiết lập khoảng thời gian vật thể phải xuất hiện trong vùng ROI trước khi phát sự kiện.
     * `Direction`: Chiều chuyển động hợp lệ.

3. **Cơ chế Kích hoạt & Truyền tin sự kiện (Triggers & Alerts)**:
   * Khi sự kiện xảy ra, hệ thống tự động sinh dữ liệu metadata (SNAPSHOT ảnh lỗi, tọa độ vật thể, mốc thời gian).
   * **Hỗ trợ tích hợp**:
     * **Webhook / HTTP Request**: Gửi dữ liệu JSON đến máy chủ bên thứ ba.
     * **MQTT / RabbitMQ / Apache Pulsar**: Đẩy tin nhắn vào hệ thống IoT hoặc hàng đợi tin nhắn của doanh nghiệp.
     * **DAQ (Data Acquisition)**: Xuất tín hiệu điện vật lý để bật đèn còi hoặc đóng ngắt thiết bị ngoại vi qua I/O.
     * **VMS (Video Management System)**: Đồng bộ luồng sự kiện với hệ thống quản lý camera tập trung.
     * **Email, Loa báo động (Audio Alert), Push Notification**.

---

### B. ANSDL (Thư viện AI dành cho National Instruments LabVIEW)
ANSDL là bộ thư viện VI (Virtual Instruments) giúp kỹ sư tự động hóa gọi trực tiếp các mô hình AI trong code LabVIEW mà không cần dùng Python/C#.

1. **Các thư viện thành phần (Sub-toolkits)**:
   * `ODHUB-LV`: Chạy mô hình phát hiện vật thể (YOLO v4, YOLO v8, YOLO v9...).
   * `DLHUB-LV`: Gọi các mô hình học sâu phân loại và phân vùng.
   * `ANNHUB-LV`: Gọi mô hình dự đoán dữ liệu số từ các cảm biến.
   * `ANSTS`: Tích hợp mô hình phát hiện dị vật/bất thường từ ANS Training Studio.
   * `ANSFR`: Nhận diện khuôn mặt (Face Recognition).
   * `ANSOCR`: Đọc ký tự từ ảnh (Optical Character Recognition) đa ngôn ngữ.
   * `ANSALPR`: Nhận diện biển số xe tự động.
   * `ANSCV`: Điều khiển camera công nghiệp và xử lý ảnh cơ bản.

2. **Thông số cấu hình API chính**:
   * `ModelType`: Chọn engine tương thích với mô hình huấn luyện (ví dụ: `ODHUB`, `ANSTS`).
   * `Model Zip Password`: Mật khẩu giải mã tệp mô hình dạng nén `.zip` để bảo vệ tài sản trí tuệ.
   * **Tối ưu hóa phần cứng**: Sử dụng bộ tăng tốc TensorRT giúp biên dịch mô hình thành file `.engine` tối ưu riêng cho card đồ họa NVIDIA chạy trên máy trạm, giảm đáng kể thời gian suy luận (Inference time).

---

## 2. Chi tiết các công cụ Thiết kế & Huấn luyện (Designing & Training)

### A. ANSTS (ANS Training Studio)
ANSTS là studio toàn diện xử lý các tác vụ thị giác máy tính cục bộ (local):

* **Labeling Tool (Công cụ dán nhãn)**: Tích hợp sẵn bộ dán nhãn hình chữ nhật (Bounding box) hoặc đa giác (Polygon). Hỗ trợ import/export linh hoạt các định dạng YOLO, Pascal VOC, JSON.
* **Tác vụ hỗ trợ**:
  * **Classification**: Phân loại ảnh.
  * **Object Detection**: Xác định vị trí vật thể.
  * **Segmentation**: Phân vùng chi tiết từng pixel (phù hợp đo đạc kích thước ngoại quan).
  * **Anomaly Detection**: Học các đặc trưng của sản phẩm chuẩn, phát hiện các điểm sai lệch/bất thường (rất hiệu quả khi không có nhiều mẫu lỗi).
* **Training (Huấn luyện)**: Chạy hoàn toàn trên phần cứng GPU NVIDIA cục bộ (Local GPU Acceleration). Cung cấp biểu đồ trực quan thời gian thực: Loss curve, Accuracy, Confusion Matrix để đánh giá mô hình.

---

### B. ANNHUB, DLHUB & ODHUB
Bộ ba Studio không code đời trước được tối ưu hóa cho từng nhiệm vụ riêng biệt:

* **ODHUB**: Chuyên biệt phát hiện vật thể. Hỗ trợ đầy đủ các framework phổ biến bao gồm TensorFlow (SSD, Faster RCNN, EfficientDet) và YOLO (v2, v3, v4).
* **ANNHUB**: Thiết kế cấu trúc mạng nơ-ron nhân tạo (ANN) tự động. Rất mạnh trong việc dự đoán lỗi thiết bị dựa trên các chỉ số cảm biến đo nhiệt độ, độ rung, dòng điện (dữ liệu số dạng bảng).
* **DLHUB**: Cho phép người dùng kéo thả các khối lớp (layers) để tùy biến cấu trúc mạng sâu và xác thực kết quả ngay trên giao diện trực quan.

---

## 3. Hệ thống bản quyền (Licensing System)

Mọi hoạt động triển khai thực tế trên các node sản xuất đều được kiểm soát bởi **License Manager**:
* **Online Activation**: Kích hoạt nhanh thông qua tài khoản đăng ký trên ANS Portal khi thiết bị có kết nối Internet.
* **Offline Activation**: Tạo file yêu cầu kích hoạt (Request File) từ License Manager trên máy offline, mang sang máy online để lấy file kích hoạt (Response File) nạp ngược lại.
* Mỗi toolkit trong ANSDL (ví dụ: `ODHUB-LV`, `ANSOCR`) và phần mềm đầu cuối `ANSVIS` đều yêu cầu một License Key độc lập.
