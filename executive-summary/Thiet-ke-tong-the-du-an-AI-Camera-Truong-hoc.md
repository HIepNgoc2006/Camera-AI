# TÀI LIỆU THIẾT KẾ TỔNG THỂ DỰ ÁN
## Hệ thống AI Camera Giám sát – Điểm danh – Phát hiện vi phạm trường học
---

## 1. TỔNG QUAN DỰ ÁN

### 1.1 Mục tiêu
Xây dựng một hệ thống khép kín gồm **Camera AI + Server xử lý + Web Portal + Mobile App (iOS/Android)** nhằm:

1. Điểm danh học sinh, giáo viên, cán bộ tự động bằng AI camera.
2. Phát hiện vi phạm hằng ngày: sai đồng phục, đi trễ, xả rác, hút thuốc, thiếu bảo hộ tại bếp ăn.
3. Chấm công cho cán bộ/giáo viên; Student Uniform được ánh xạ vào nhóm camera phù hợp trong 34 camera hiện có.
4. Cung cấp web/app cho **phụ huynh** và **ban giám hiệu (BGH)** theo dõi số liệu điểm danh và vi phạm theo thời gian thực.

### 1.2 Phạm vi (Scope)

> ⚠️ **Lưu ý phạm vi quan trọng:** Team dev **chỉ chịu trách nhiệm phần mềm** (backend, AI model, web, app, bảo mật). Các khâu **khảo sát hiện trường, mua sắm/lắp đặt phần cứng camera, đi dây mạng** do bên khác (khách hàng hoặc đơn vị thi công riêng) thực hiện. Team dev chỉ cần **camera/NVR đã được lắp đặt và cung cấp luồng dữ liệu (RTSP/ONVIF) hoặc API** để tích hợp.

| Trong phạm vi (Dev team) | Ngoài phạm vi (bên khác thực hiện) |
|---|---|
| Backend, database, AI model (điểm danh, phát hiện vi phạm) | Khảo sát hiện trường, chọn vị trí lắp camera |
| Web Portal (phụ huynh + BGH) | Mua sắm, lắp đặt, đi dây camera/NVR |
| Mobile App (React Native — iOS & Android) | Thi công hạ tầng mạng vật lý tại trường |
| Bảo mật hệ thống (mã hoá, RBAC, kiểm thử bảo mật) | Bảo trì phần cứng camera sau lắp đặt |
| Tích hợp với luồng camera (RTSP/ONVIF) đã có sẵn | |
| **Không giám sát bên trong lớp học** | |

### 1.3 Đối tượng sử dụng
- **Phụ huynh:** xem điểm danh, vi phạm của con qua App/Web.
- **Ban giám hiệu/ban cán bộ trường:** xem tổng quan toàn trường, xuất báo cáo.
- **Cán bộ/giáo viên:** chấm công, xem đánh giá cá nhân.
- **Dev team:** triển khai, vận hành, bảo trì hệ thống.

---

## 2. KIẾN TRÚC TỔNG THỂ HỆ THỐNG

```
┌─────────────────────────────────────────────────────────────────┐
│                        LỚP CAMERA (34 cái)                       │
│   Cổng | Sân trường | Hành lang | Bếp ăn  (KHÔNG lắp trong lớp)  │
└───────────────────────────┬───────────────────────────────────────┘
                            │ RTSP/ONVIF stream
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                LỚP EDGE AI (ANSVIS/AIBOX tại trường)              │
│  - Face Detection + Facial Recognition cho điểm danh/chấm công    │
│  - AI Task / model / ROI / rule / Event Log / HTTP Trigger        │
│  - 4 pipeline cần kiểm chứng riêng: rác, thuốc lá, đồng phục, PPE │
└───────────────────────────┬───────────────────────────────────────┘
                            │ HTTPS/MQTT (mã hoá)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SERVER TRUNG TÂM (Cloud/On-prem)              │
│  API Gateway → ANSVIS Adapter → Service Backend → Message Queue   │
│  Database (PostgreSQL) | Object Storage (ảnh/video vi phạm)       │
│  Cache (Redis) | Monitoring (Prometheus/Grafana)                  │
└───────────────┬─────────────────────────────┬─────────────────────┘
                ▼                             ▼
      ┌──────────────────┐         ┌───────────────────────┐
      │   WEB PORTAL      │         │   MOBILE APP (1 code) │
      │ Phụ huynh + BGH   │         │  iOS + Android         │
      │ Dashboard, báo cáo│         │  Push notification      │
      └──────────────────┘         └───────────────────────┘
```

**Nguyên tắc thiết kế:** xử lý video/AI Task càng nhiều ở **ANSVIS/AIBOX tại trường** càng tốt. Backend không đọc trực tiếp toàn bộ luồng camera nếu ANSVIS đã là tầng AI chính; Backend nhận event qua HTTP Trigger, validate, chuẩn hóa, lưu dữ liệu nghiệp vụ và hiển thị trên Web/Mobile.

---

## 3. HỆ THỐNG CAMERA AI (34 camera)

### 3.1 Bảng phân bổ

| Nhóm chức năng | Số lượng | Khu vực lắp đặt | Mục đích |
|---|---|---|---|
| Điểm danh/chấm công/đồng phục | **16** | Cổng trường, sân trường, hành lang chính | Nhận diện HS-GV ra vào, điểm danh, chấm công và hỗ trợ Student Uniform theo mapping đã khóa |
| Phát hiện xả rác | 8 | Sân trường, khu vực công cộng | Phát hiện hành vi xả rác sai quy định |
| Phát hiện hút thuốc | 8 | Khu vực ngoài trời, hành lang, gần cổng | Phát hiện hành vi hút thuốc |
| Vi phạm đồng phục/bảo hộ bếp ăn | 2 | Khu vực bếp ăn | Giám sát đồng phục, bảo hộ ATTP tại bếp |
| **Tổng cộng** | **34** | | |

*(16 camera điểm danh/đánh giá + 18 camera phát hiện vi phạm = 34 camera, đúng như số liệu đã cung cấp: 8+8+2=18)*

### 3.2 Thông số camera đề xuất
- Độ phân giải: tối thiểu **4MP (2K)**, khuyến nghị 4K cho khu vực cổng/bếp (cần độ nét cao để nhận diện chi tiết đồng phục, khuôn mặt).
- Hồng ngoại (IR) ban đêm ≥ 30m cho khu vực ngoài trời.
- Chuẩn PoE (Power over Ethernet) để giảm dây nguồn riêng, dễ triển khai.
- Góc rộng (wide-angle) cho sân trường, ống kính tiêu chuẩn cho cổng/hành lang (nhận diện khuôn mặt cần góc thẳng).
- Chuẩn ONVIF để tương thích đa hãng, tránh khoá vendor.

### 3.3 Các bài toán AI cần triển khai

| Bài toán | Hướng xử lý theo ANSVIS-first | Ghi chú |
|---|---|---|
| Điểm danh học sinh | Dùng `Face Detection` + `Facial Recognition` có sẵn trong ANSVIS | Backend xử lý lớp, lịch học, có mặt/vắng/đi muộn/check-in/check-out |
| Chấm công giáo viên/cán bộ | Dùng chung nền tảng Facial Recognition | Backend xử lý ca làm, giờ vào/ra, đi muộn, về sớm, báo cáo tháng |
| Phát hiện xả rác | Custom Littering Detection pipeline | Không chỉ nhận diện `garbage`; cần person/object tracking, ROI, vùng bỏ rác hợp lệ, logic vật bị bỏ lại |
| Phát hiện hút thuốc | Custom Smoking Detection pipeline | Chỉ nên trả kết quả `nghi vấn hút thuốc`, bắt buộc human review vì dễ nhầm bút/điện thoại/ăn uống |
| Đồng phục học sinh | Custom Student Uniform Detection pipeline | Cần chốt quy định đồng phục thật của trường: áo/quần/váy/thẻ/logo/màu sắc/giày nếu áp dụng |
| Bảo hộ bếp ăn | Custom Kitchen PPE Detection pipeline | Cần rule cho mũ, khẩu trang, tạp dề, găng tay, đồng phục bếp, giày bảo hộ |
| Happiness index | Chỉ triển khai nếu được phê duyệt rõ về mục đích/consent | Khuyến nghị dùng mức tổng hợp/xu hướng, không dùng làm đánh giá cá nhân chính thức |

Ghi chú quan trọng: video tập huấn ANSVIS/AIBOX chứng minh nền tảng có cơ chế cấu hình camera, AI Task, model, ROI/rule, Event Log và HTTP Trigger. Video không chứng minh sẵn model production cho toàn bộ 6 nghiệp vụ. Vì vậy 4 pipeline vi phạm phải qua spec → baseline → shadow mode → evaluate → train/fine-tune nếu cần → nghiệm thu.

### 3.4 Lưu ý về pháp lý & quyền riêng tư (quan trọng)
- Dữ liệu sinh trắc học (khuôn mặt) của học sinh là **dữ liệu cá nhân nhạy cảm**, đặc biệt với trẻ em. Việt Nam có quy định về bảo vệ dữ liệu cá nhân (Nghị định 13/2023/NĐ-CP) yêu cầu có sự đồng ý của phụ huynh/người giám hộ khi thu thập dữ liệu sinh trắc học của trẻ. Đây là lưu ý mang tính tham khảo, đề nghị trường/dev team xác nhận lại với bộ phận pháp lý trước khi triển khai chính thức.
- Nên có: (1) form đồng ý (consent) cho phụ huynh khi đăng ký, (2) chính sách lưu trữ/xoá dữ liệu ảnh vi phạm sau X ngày, (3) phân quyền chặt để phụ huynh chỉ xem được dữ liệu của con mình.
- Không lắp camera trong lớp học — đúng như yêu cầu, giúp giảm rủi ro pháp lý và tăng sự chấp thuận từ phụ huynh/giáo viên.

---

## 4. HẠ TẦNG SERVER & BACKEND

### 4.1 Đề xuất kiến trúc kỹ thuật

| Thành phần | Công nghệ đề xuất | Lý do |
|---|---|---|
| API Backend | Node.js (NestJS) hoặc Python (FastAPI) | Hiệu năng tốt, hệ sinh thái AI mạnh (đặc biệt Python cho inference) |
| AI Inference Service | Python + Triton Inference Server / ONNX Runtime, chạy trên GPU | Tối ưu tốc độ xử lý real-time cho 34 luồng camera |
| Message Queue | Kafka hoặc RabbitMQ | Đảm bảo không mất dữ liệu khi lượng sự kiện tăng đột biến (giờ tan học) |
| Database | PostgreSQL (dữ liệu quan hệ: điểm danh, vi phạm, người dùng) | Ổn định, hỗ trợ transaction tốt |
| Cache | Redis | Giảm tải truy vấn dashboard real-time |
| Object Storage | S3-compatible (MinIO on-prem hoặc AWS S3) | Lưu ảnh/clip vi phạm |
| Giám sát hạ tầng | Prometheus + Grafana | Theo dõi tỷ lệ sử dụng CPU/RAM/GPU/băng thông server real-time |
| Container hoá | Docker + Kubernetes (hoặc Docker Compose nếu quy mô 1 trường) | Dễ scale, dễ rollback |

### 4.2 Ước tính tải hệ thống (sizing) — cần dev team xác nhận thực tế
- 34 camera stream liên tục → khuyến nghị **edge box AI tại trường** đảm nhận inference (giảm băng thông upload), server trung tâm chỉ nhận metadata + ảnh sự kiện.
- Server trung tâm cần tối thiểu: GPU (nếu chạy thêm inference tập trung), 32–64GB RAM, SSD NVMe cho database, băng thông ổn định ≥ 100Mbps upload dành riêng cho hệ thống camera.
- Backup: snapshot database hằng ngày + lưu trữ ảnh vi phạm tối thiểu 30–90 ngày (tuỳ chính sách trường).

### 4.3 Chỉ tiêu hiệu năng (SLA nội bộ đề xuất)
| Chỉ tiêu | Mục tiêu |
|---|---|
| Độ trễ phát hiện vi phạm → hiển thị trên app | < 5 giây |
| Uptime server | ≥ 99.5% |
| Tỷ lệ nhận diện điểm danh chính xác | ≥ 95% (điều kiện ánh sáng tốt) |
| Tỷ lệ sử dụng CPU/GPU trung bình | Cảnh báo khi > 75%, auto-scale khi có |

### 4.4 Kiểm tra tỷ lệ sử dụng server
- Thiết lập dashboard Grafana theo dõi: CPU, RAM, GPU, disk I/O, băng thông mạng, số lượng request/giây, độ trễ pipeline AI.
- Cảnh báo (alert) tự động qua Slack/Email khi tài nguyên vượt ngưỡng — để dev team phản ứng trước khi ảnh hưởng người dùng.

---

## 5. WEB PORTAL (Phụ huynh + Ban giám hiệu)

### 5.1 Tính năng chính
- **Dành cho phụ huynh:** xem điểm danh con theo ngày/tháng, lịch sử vi phạm (kèm ảnh minh chứng), thông báo tức thời.
- **Dành cho BGH/ban cán bộ:** dashboard tổng quan toàn trường — số HS/GV có mặt, tỷ lệ đi trễ, tổng vi phạm theo loại (đồng phục/rác/thuốc lá/bảo hộ bếp), biểu đồ xu hướng theo tuần/tháng, xuất báo cáo Excel/PDF.
- **Dành cho cán bộ/giáo viên:** xem lịch sử chấm công cá nhân và thông tin nghiệp vụ đúng phạm vi được phân quyền.

### 5.2 Phân quyền (Role-based access)
| Vai trò | Quyền truy cập |
|---|---|
| Phụ huynh | Chỉ xem dữ liệu của con mình |
| Giáo viên | Xem dữ liệu lớp phụ trách + cá nhân |
| BGH/Ban cán bộ | Xem toàn trường, xuất báo cáo, quản lý người dùng |
| Admin hệ thống (dev team) | Toàn quyền vận hành, cấu hình |

### 5.3 Công nghệ đề xuất
- Frontend: React (Next.js) — tối ưu SEO nếu cần, tốc độ tải nhanh.
- Biểu đồ: Recharts/Chart.js cho dashboard thống kê.

---

## 6. MOBILE APP (iOS & Android — đồng bộ, React Native)

### 6.1 Chiến lược "1 codebase, 2 nền tảng"
Sử dụng **React Native** để phát triển đồng thời cho cả iOS & Android. Lợi ích:
- Một đội dev duy nhất maintain, tránh lệch tính năng giữa 2 hệ điều hành.
- Tốc độ ra mắt nhanh hơn, phù hợp deadline 1 tháng.
- Hệ sinh thái thư viện lớn, dễ tích hợp các thư viện bảo mật (certificate pinning, secure storage, biometric auth) sẵn có cho cả 2 nền tảng.
- Có thể viết native module riêng (Swift/Kotlin) khi cần tối ưu hiệu năng xử lý camera/notification ở tầng hệ điều hành.

### 6.2 Tính năng chính
- Đăng nhập/phân quyền giống Web Portal.
- Push notification: điểm danh thành công, phát hiện vi phạm, đi trễ.
- Xem lịch sử điểm danh/vi phạm kèm ảnh.
- Với cán bộ/giáo viên: xem chấm công và thông báo nghiệp vụ theo quyền.

### 6.3 Rủi ro cần lưu ý
- **Apple App Store review** có thể mất 1–3 ngày (đôi khi lâu hơn nếu bị từ chối lần đầu) — cần nộp bản build sớm, không để sát deadline cuối tháng.
- Google Play thường duyệt nhanh hơn nhưng vẫn cần thời gian buffer.

---

## 8. QUY TRÌNH PHÁT TRIỂN (DEV TEAM)

### 8.1 Quy trình nội bộ
1. **Sprint planning** (chia theo tuần, xem mục 9 – Timeline).
2. **Git flow:** nhánh `main` (production), `develop` (tích hợp), `feature/*` (tính năng riêng).
3. **CI/CD:** tự động build & test khi merge vào `develop`; deploy staging tự động; deploy production cần approval thủ công.
4. **Code review bắt buộc** trước khi merge — đặc biệt với module AI (độ chính xác model ảnh hưởng trực tiếp đến uy tín hệ thống).

### 8.2 Quy trình cài đặt trên server (dev team thực hiện)
1. Chuẩn bị hạ tầng (server/cloud instance, GPU nếu cần) → cấu hình theo mục 4.
2. Deploy database, message queue, storage trước.
3. Deploy backend service + AI inference service, kết nối tới **luồng camera đã có sẵn** (RTSP/ONVIF do bên lắp đặt phần cứng bàn giao thông tin kết nối) — dev team không cần ra hiện trường.
4. Deploy web portal + kết nối API.
5. Build & submit mobile app (React Native) lên App Store/Google Play.
6. Kiểm thử tích hợp toàn trình (end-to-end test) qua kết nối từ xa với luồng camera thực tế hoặc dữ liệu mẫu do bên lắp đặt cung cấp.
7. Giám sát 24–48h đầu sau go-live để phát hiện lỗi phát sinh (hyper-care period).

---

## 9. QUY TRÌNH HƯỚNG DẪN & CÀI ĐẶT CHO PHỤ HUYNH & BAN CÁN BỘ TRƯỜNG

### 9.1 Quy trình 5 bước cho phụ huynh
1. Nhận thông tin đăng ký tài khoản (qua nhà trường phát mã QR/link mời).
2. Tải App (link riêng cho iOS/Android) hoặc truy cập Web Portal.
3. Đăng nhập, xác nhận thông tin con em (liên kết học sinh với tài khoản phụ huynh).
4. Đồng ý chính sách thu thập dữ liệu (consent form) — bắt buộc trước khi kích hoạt tính năng nhận diện khuôn mặt cho con.
5. Nhận hướng dẫn sử dụng nhanh (video/PDF 1 trang) — cách xem điểm danh, vi phạm, cách bật/tắt thông báo.

### 9.2 Quy trình cho ban cán bộ/BGH
1. Buổi đào tạo trực tiếp (1–2 giờ) giới thiệu dashboard, cách đọc báo cáo.
2. Tài liệu hướng dẫn chi tiết (PDF/slide) + video demo lưu trữ nội bộ.
3. Kênh hỗ trợ kỹ thuật (hotline/Zalo nhóm) trong giai đoạn đầu triển khai (2–4 tuần đầu).
4. Buổi review sau 2 tuần sử dụng để thu thập phản hồi, điều chỉnh.

### 9.3 Tài liệu cần chuẩn bị
- Hướng dẫn sử dụng App/Web (dạng hình ảnh, ngắn gọn).
- FAQ thường gặp (quên mật khẩu, không nhận được thông báo, sai thông tin điểm danh...).
- Form đồng ý thu thập dữ liệu sinh trắc học (consent form).

---

## 10. TIMELINE THỰC TẾ CHO 1 DEV (ước tính ~7–8 tháng nếu làm đầy đủ, cẩn thận)

### 10.1 Vì sao không thể giữ 1 tháng?
Kế hoạch ban đầu (4 tuần) giả định có **nhiều người làm song song** (backend, AI, mobile, web, DevOps, QA chạy đồng thời). Với **1 developer**, phần lớn công việc phải làm **tuần tự** (không thể vừa code backend vừa code app cùng lúc), nên tổng thời gian gần bằng **tổng cộng dồn** của từng phần việc, không phải thời gian của phần việc dài nhất. Đây là lý do timeline thực tế dài hơn nhiều so với bản 1 tháng.

> Ước tính dưới đây giả định: dev làm full-time, ANSVIS/AIBOX là tầng xử lý video/AI chính, Web/App/Backend build bằng mock/sanitized event trước, camera phần cứng do bên khác lắp đặt và bàn giao đúng hạn. Facial Recognition dùng model có sẵn; 4 pipeline vi phạm chỉ train/fine-tune nếu baseline/shadow mode không đạt.

### 10.2 Chi tiết theo giai đoạn

| Giai đoạn | Nội dung | Thời gian ước tính |
|---|---|---|
| **1. Chốt yêu cầu & thiết kế kỹ thuật** | Chốt requirement, thiết kế database/API, thiết kế kiến trúc bảo mật (threat model), thiết kế UI/UX cơ bản cho web & app | 2 tuần |
| **2. Backend & hạ tầng nền tảng** | Dựng server, database, message queue, xác thực (JWT/OAuth2 + MFA), API Gateway, cấu hình firewall/VPN/secret manager | 3 tuần |
| **3. Product Platform core** | Auth/RBAC/ABAC, dữ liệu trường học, consent, audit, PostgreSQL, object storage, notification/report nền tảng | 3 tuần |
| **4. ANSVIS Integration** | ANSVIS Adapter, HTTP Trigger contract, validate/normalize/idempotency, camera/task registry, mock/sanitized event cho đủ 6 chức năng | 3 tuần |
| **5. Attendance & Timekeeping** | Tích hợp Face Detection/Facial Recognition có sẵn, xử lý điểm danh/chấm công bằng rule backend, low-confidence review | 2.5 tuần |
| **6. Web Portal** | Dashboard phụ huynh/BGH/GV/admin, review queue, camera/task/event health, báo cáo/export có audit | 3 tuần |
| **7. Mobile App (React Native)** | Đăng nhập, điểm danh, thông báo, chi tiết sự kiện theo quyền, secure token storage, production hardening | 4 tuần |
| **8. AI Pipeline vi phạm** | Spec/baseline/shadow cho Kitchen PPE → Student Uniform → Littering → Smoking; train/fine-tune chỉ nếu baseline không đạt | 5–7 tuần |
| **9. Bảo mật chuyên sâu & rà soát toàn hệ thống** | OWASP review, vulnerability scan, secret/log masking, backup/restore, incident response, DDoS/webhook flood guard | 2.5 tuần |
| **10. Kiểm thử tích hợp End-to-End** | Test toàn trình với mock/staging/pilot camera, performance baseline 34 camera, UAT bug fixing | 2 tuần |
| **11. Đào tạo, tài liệu & Go-live** | Hướng dẫn sử dụng, runbook vận hành, submit app nếu cần, go-live theo đợt, hyper-care | 1.5 tuần |
| **TỔNG CỘNG** | | **~31–34 tuần (~7–8 tháng)** |

*Ghi chú: thời gian có thể rút ngắn nếu triển khai theo đợt, ANSVIS model/rule hiện có đáp ứng tốt, camera/RTSP được bàn giao sớm và UAT ít phát sinh sửa đổi. Tuy nhiên không nên cắt giảm bảo mật, consent, audit, backup/restore hoặc shadow mode để rút ngắn tiến độ.*

### 10.3 Gợi ý để rút ngắn thời gian (nếu cần)
Nếu cần rút ngắn tiến độ, có 2 hướng thực tế nhưng không đánh đổi chất lượng bảo mật:
1. **Triển khai theo đợt (phased rollout):** go-live trước với Product Platform + điểm danh/chấm công + dashboard/review queue; 4 pipeline vi phạm bật dần sau shadow mode.
2. **Tận dụng tối đa model/rule có sẵn trong ANSVIS:** chỉ train/fine-tune khi baseline thực tế không đạt; tránh biến training thành điều kiện chặn Web/App/Backend.

Việc **cắt giảm phần bảo mật để rút ngắn thời gian không được khuyến nghị**, do hệ thống xử lý dữ liệu sinh trắc học trẻ em — rủi ro pháp lý/uy tín nếu xảy ra sự cố cao hơn nhiều so với thời gian tiết kiệm được.

---

## 11. BẢO MẬT HỆ THỐNG (SECURITY BY DESIGN)

Do hệ thống xử lý **dữ liệu sinh trắc học của trẻ em, hình ảnh khuôn mặt, và dữ liệu chấm công cán bộ**, bảo mật phải được đặt làm **ưu tiên hàng đầu, xuyên suốt mọi lớp của hệ thống** — không phải là bước bổ sung ở cuối dự án.

### 11.1 Nguyên tắc thiết kế bảo mật
- **Security by Design:** bảo mật được thiết kế ngay từ kiến trúc (mục 2), không chờ đến khi hoàn thiện mới "vá" thêm.
- **Least Privilege:** mỗi vai trò/tài khoản chỉ có quyền truy cập tối thiểu cần thiết.
- **Defense in Depth:** nhiều lớp bảo vệ (mạng → server → ứng dụng → dữ liệu), một lớp bị lỗi không làm sập toàn hệ thống.
- **Zero Trust nội bộ:** mọi request giữa các service đều phải xác thực, kể cả trong cùng mạng nội bộ.

### 11.2 Bảo mật hạ tầng & mạng camera
| Hạng mục | Biện pháp |
|---|---|
| Mạng camera | Đặt camera trên **VLAN riêng biệt**, cách ly hoàn toàn khỏi mạng Wi-Fi công cộng/học sinh, chỉ NVR/AI box được phép truy cập |
| Truy cập từ xa vào server | Bắt buộc qua **VPN** hoặc bastion host, không mở cổng quản trị (SSH/RDP) trực tiếp ra Internet |
| Firewall | Whitelist theo IP/port cụ thể, chặn mặc định (deny by default) |
| Camera firmware | Đổi mật khẩu mặc định ngay khi lắp đặt, cập nhật firmware định kỳ, tắt các dịch vụ không cần thiết (UPnP, telnet...) |

### 11.3 Bảo mật dữ liệu
| Hạng mục | Biện pháp |
|---|---|
| Dữ liệu truyền (in-transit) | TLS 1.2+ bắt buộc cho toàn bộ API, RTSP stream nội bộ cũng nên mã hoá nếu đi qua mạng không tin cậy |
| Dữ liệu lưu trữ (at-rest) | Mã hoá database (encryption at rest), mã hoá riêng cho dữ liệu sinh trắc học (face embedding) — **không lưu ảnh khuôn mặt gốc nếu không bắt buộc, ưu tiên lưu vector đặc trưng (embedding) đã mã hoá** |
| Backup | Bản backup cũng phải mã hoá, kiểm soát quyền truy cập riêng, test khôi phục định kỳ |
| Vòng đời dữ liệu | Chính sách xoá tự động ảnh/clip vi phạm sau X ngày (theo thoả thuận với trường), quyền yêu cầu xoá dữ liệu của phụ huynh (right to erasure) |
| Ẩn danh hoá cho happiness index | Chỉ số hạnh phúc xử lý theo hướng tổng hợp/thống kê, không lưu gắn trực tiếp với danh tính cá nhân ở mức chi tiết |

### 11.4 Xác thực & phân quyền (AuthN/AuthZ)
| Hạng mục | Biện pháp |
|---|---|
| Xác thực người dùng | JWT (access token thời hạn ngắn + refresh token), hash mật khẩu bằng bcrypt/Argon2 |
| MFA (xác thực 2 lớp) | **Bắt buộc cho tài khoản Admin & BGH**, khuyến khích cho giáo viên; tuỳ chọn cho phụ huynh |
| Phân quyền (RBAC) | Áp dụng chi tiết theo bảng phân quyền ở Mục 5.2, kiểm tra quyền ở **cả tầng API lẫn tầng giao diện** (không chỉ ẩn nút bấm) |
| Session management | Tự động hết hạn phiên đăng nhập sau thời gian không hoạt động, cho phép người dùng thu hồi phiên đăng nhập từ thiết bị khác |

### 11.5 Bảo mật API & Backend
- Áp dụng rà soát theo **OWASP Top 10** (SQL Injection, Broken Access Control, Injection, Security Misconfiguration...).
- Input validation & sanitization ở mọi endpoint nhận dữ liệu từ client.
- Rate limiting/throttling để chống brute-force và DDoS cơ bản.
- API Gateway kiểm soát tập trung: xác thực, logging, giới hạn tốc độ trước khi vào service nội bộ.
- Secrets (API key, DB credential) lưu trong **secret manager** (Vault/AWS Secrets Manager...), tuyệt đối không hard-code trong source code.

### 11.6 Bảo mật Mobile App (React Native)
- **Secure Storage:** token/thông tin nhạy cảm lưu bằng Keychain (iOS) / Keystore (Android) qua thư viện secure storage, không lưu plaintext trong AsyncStorage.
- **Certificate Pinning:** app chỉ tin tưởng đúng certificate của server, chống tấn công man-in-the-middle.
- **Code obfuscation:** làm rối mã nguồn bản build production để hạn chế reverse-engineering.
- **Root/Jailbreak detection:** cảnh báo hoặc hạn chế tính năng nhạy cảm trên thiết bị đã bị can thiệp hệ điều hành.
- Không log dữ liệu nhạy cảm (token, ảnh khuôn mặt) ra console trong bản production.

### 11.7 Giám sát bảo mật & phản ứng sự cố
| Hạng mục | Biện pháp |
|---|---|
| Audit log | Ghi log mọi hành động nhạy cảm (đăng nhập, xem dữ liệu vi phạm, thay đổi quyền, xuất báo cáo) — không thể chỉnh sửa/xoá bởi user thường |
| Giám sát bất thường | Cảnh báo khi có đăng nhập bất thường (nhiều lần sai, địa điểm lạ), khi có truy vấn dữ liệu số lượng lớn bất thường |
| Kế hoạch phản ứng sự cố (Incident Response Plan) | Quy trình xác định – cô lập – khắc phục – thông báo (kể cả thông báo cho nhà trường/phụ huynh nếu có rò rỉ dữ liệu), phân công rõ ai chịu trách nhiệm xử lý sự cố |
| Kiểm thử bảo mật định kỳ | Vulnerability scan tự động (SAST/DAST) trong CI/CD; khuyến nghị pentest bởi bên thứ ba định kỳ (6–12 tháng/lần), tối thiểu 1 lượt kiểm tra bảo mật cơ bản trước go-live |

### 11.8 Tuân thủ pháp lý về dữ liệu cá nhân trẻ em
- Tham chiếu quy định bảo vệ dữ liệu cá nhân hiện hành tại Việt Nam (đặc biệt liên quan dữ liệu sinh trắc học, dữ liệu trẻ em) — cần bộ phận pháp lý của trường/đối tác xác nhận cụ thể trước khi thu thập dữ liệu khuôn mặt học sinh.
- Bắt buộc có **form đồng ý (consent) rõ ràng từ phụ huynh** trước khi kích hoạt tính năng nhận diện khuôn mặt cho con em.
- Có chính sách bảo mật (Privacy Policy) công khai, minh bạch về: dữ liệu gì được thu thập, lưu bao lâu, ai được truy cập, cách yêu cầu xoá dữ liệu.

### 11.9 Checklist bảo mật trước khi go-live
- [ ] TLS được cấu hình đúng trên toàn bộ endpoint (không còn HTTP thuần)
- [ ] Mật khẩu mặc định trên camera/NVR đã được đổi
- [ ] Secrets không còn hard-code trong code/repo
- [ ] RBAC đã test đầy đủ (không thể truy cập chéo dữ liệu giữa các phụ huynh)
- [ ] MFA đã bật cho tài khoản Admin/BGH
- [ ] Backup đã test khôi phục thành công ít nhất 1 lần
- [ ] Đã chạy vulnerability scan cơ bản, không còn lỗ hổng mức Critical/High chưa xử lý
- [ ] Form đồng ý thu thập dữ liệu sinh trắc học đã sẵn sàng cho phụ huynh
- [ ] Incident Response Plan đã có và team biết quy trình xử lý khi có sự cố

---

## 12. RỦI RO & KHUYẾN NGHỊ

| Rủi ro | Mức độ | Khuyến nghị |
|---|---|---|
| Deadline 1 tháng ban đầu không khả thi với 1 dev cho toàn bộ scope (34 camera, 6 chức năng AI, web, app 2 nền tảng, bảo mật) | **Cao** | Đã điều chỉnh timeline thực tế thành ~7–8 tháng nếu làm đầy đủ (Mục 10); nếu bên mua cần rút ngắn, áp dụng phased rollout thay vì cắt bảo mật |
| 1 dev là điểm nghẽn duy nhất (single point of failure) — nếu ốm/nghỉ, cả dự án dừng lại | Trung bình | Ghi chép tài liệu kỹ thuật đầy đủ trong lúc code (để người khác có thể tiếp nhận nếu cần), backup code thường xuyên lên remote repo |
| Độ chính xác pipeline AI đặc thù, đặc biệt hút thuốc và xả rác, chưa thể cam kết nếu chưa shadow mode bằng camera thật | Cao | Chạy capability gate, baseline, shadow mode; chỉ train/fine-tune khi model/rule có sẵn không đạt |
| Thời gian duyệt App Store (Apple) có thể trễ | Trung bình | Submit bản build sớm nhất có thể, không để sát ngày cuối |
| Vấn đề pháp lý về dữ liệu sinh trắc học trẻ em | Cao | Chuẩn bị form đồng ý phụ huynh + tham vấn pháp lý trước khi thu thập dữ liệu khuôn mặt học sinh |
| Thời gian lắp đặt phần cứng (camera, dây mạng, PoE) có thể phát sinh do điều kiện hiện trường | Trung bình | **Không thuộc phạm vi dev team** — đây là rủi ro của bên lắp đặt phần cứng. Dev team cần yêu cầu bên đó cam kết mốc thời gian bàn giao luồng camera (RTSP/ONVIF) đúng hạn, vì đây là **phụ thuộc đầu vào bắt buộc** để dev có thể tích hợp và test |
| "Chỉ số hạnh phúc" dựa trên nhận diện cảm xúc còn hạn chế về độ chính xác | Trung bình | Dùng như chỉ số tham khảo/xu hướng tổng hợp, không dùng để đánh giá cá nhân chính thức |
| Deadline gấp có thể khiến team cắt giảm bước kiểm thử bảo mật để kịp go-live | **Cao** | Bảo mật (mã hoá, RBAC, secrets) phải làm **song song từ đầu**, không để dồn vào cuối; nếu thiếu thời gian, ưu tiên hoãn go-live hơn là bỏ qua checklist bảo mật ở Mục 11.9 |
| Rò rỉ dữ liệu sinh trắc học/hình ảnh học sinh | **Cao** | Áp dụng đầy đủ Mục 11 (mã hoá, RBAC, audit log), hạn chế lưu ảnh gốc, có Incident Response Plan rõ ràng |

---

## 13. TÓM TẮT CÁC THÔNG SỐ CHÍNH

| Hạng mục | Thông số |
|---|---|
| Tổng số camera | 34 (16 điểm danh/đánh giá + 18 phát hiện vi phạm) |
| Khu vực giám sát | Cổng, sân trường, hành lang, bếp ăn (không có trong lớp học) |
| Nền tảng app | 1 codebase **React Native** cho iOS & Android |
| Web portal | Phụ huynh + BGH, phân quyền theo vai trò (RBAC) |
| Backend | Node.js/Python + PostgreSQL + Redis + Kafka |
| AI inference | ANSVIS/AIBOX-first; Facial Recognition có sẵn; 4 pipeline custom kiểm chứng bằng baseline/shadow mode |
| Giám sát hạ tầng | Prometheus/Grafana theo dõi tỷ lệ sử dụng server real-time |
| Bảo mật | Mã hoá toàn trình (in-transit + at-rest), RBAC, MFA cho admin/BGH, mạng camera cô lập (VLAN), audit log, kiểm thử bảo mật trước go-live (xem Mục 11) |
| Đội ngũ | 1 developer (full-stack + AI + mobile) |
| Deadline | Ban đầu 1 tháng → thực tế ~7–8 tháng nếu 1 dev làm đầy đủ/cẩn thận; có thể rút ngắn bằng phased rollout |

---

*Tài liệu này là bản thiết kế tổng thể (blueprint) ở mức kiến trúc/kế hoạch. Trước khi triển khai chính thức, khuyến nghị dev team làm rõ thêm: ngân sách phần cứng cụ thể, hạ tầng cloud/on-prem sẵn có, và xác nhận pháp lý về thu thập dữ liệu sinh trắc học trẻ em với bộ phận liên quan.*
