# KẾ HOẠCH PHÁT TRIỂN PHẦN MỀM HỆ THỐNG AI CAMERA TRƯỜNG HỌC
---

## 1. Tóm tắt điều hành

Dự án xây dựng hệ thống phần mềm AI Camera cho trường học, tích hợp 34 camera đã được bên khác cung cấp/lắp đặt. Hệ thống gồm lớp phân tích video AI, backend, cơ sở dữ liệu, Web Portal, ứng dụng React Native cho iOS/Android, thông báo, báo cáo, bảo mật và công cụ vận hành.

Các nghiệp vụ chính:

- Điểm danh học sinh tự động.
- Chấm công cán bộ, giáo viên.
- Happiness index là Optional/Future Scope, không thuộc baseline sáu chức năng hiện tại và không chặn kế hoạch triển khai.
- Phát hiện đi trễ, sai đồng phục, xả rác, hút thuốc và thiếu bảo hộ tại bếp ăn.
- Cung cấp thông tin phù hợp cho phụ huynh, giáo viên, ban giám hiệu và quản trị viên.
- Tích hợp nền tảng ANSCENTER để huấn luyện/triển khai model và xử lý video tại chỗ khi khả năng phiên bản/license đáp ứng yêu cầu.

Phạm vi của đội phát triển chỉ bao gồm **phần mềm**. Khảo sát hiện trường, mua sắm/lắp camera, kéo dây, cấp nguồn và thi công mạng vật lý không nằm trong kế hoạch này.

Kế hoạch được lập theo giả định hiện tại có **01 developer** thực hiện toàn bộ backend, AI, web, mobile, bảo mật và triển khai. Vì vậy công việc phải được ưu tiên và thực hiện tuần tự. Tài liệu này chưa cam kết ngày hoàn thành; lịch chính thức là nội dung đàm phán sau khi ban lãnh đạo chốt phạm vi, nguồn lực và trách nhiệm cung cấp đầu vào.

## 2. Nội dung cần Ban lãnh đạo quyết định

| Mã | Quyết định cần phê duyệt | Khuyến nghị |
|---|---|---|
| QĐ-01 | Phạm vi phiên bản đầu tiên | Giữ đủ các module bắt buộc nhưng cho phép triển khai theo đợt; ưu tiên nền tảng, điểm danh và một số vi phạm trọng yếu trước |
| QĐ-02 | Mô hình nguồn lực | Xác định rõ chấp nhận một developer làm tuần tự hay bổ sung nguồn lực cho QA/bảo mật/mobile/AI |
| QĐ-03 | Mức phụ thuộc ANSCENTER | Dùng ANSVIS/ANSTS cho video analytics khi API, license và số kênh được xác nhận; giữ backend nghiệp vụ độc lập qua lớp adapter |
| QĐ-04 | Chủ thể chịu trách nhiệm pháp lý dữ liệu | Nhà trường là đơn vị quyết định mục đích xử lý và phê duyệt consent/chính sách; đội phát triển triển khai kiểm soát kỹ thuật |
| QĐ-05 | Chính sách lưu dữ liệu | Chốt loại dữ liệu được lưu, thời hạn lưu snapshot/video/embedding/log và quy trình xóa |
| QĐ-06 | Chỉ tiêu nghiệm thu AI | Chỉ khóa sau khi nhận dataset đại diện; không cam kết độ chính xác tuyệt đối trước khi đánh giá dữ liệu thật |
| QĐ-07 | Mức hỗ trợ sau go-live | Chốt thời gian hyper-care, giờ hỗ trợ, SLA và phạm vi bảo hành/bảo trì |
| QĐ-08 | Quyền sở hữu và license | Chốt quyền sở hữu source code, model, dataset, artifact và trách nhiệm mua/duy trì license bên thứ ba |

## 3. Phạm vi dự án

### 3.1 Trong phạm vi

| Nhóm | Nội dung |
|---|---|
| Phân tích và thiết kế | Yêu cầu, use case, kiến trúc, dữ liệu, API, UX flow, threat model và kế hoạch nghiệm thu |
| AI và video analytics | Tích hợp ANSVIS/AIBOX; cấu hình AI Task/model/ROI/rule; dùng Facial Recognition có sẵn cho điểm danh/chấm công; thiết kế 4 pipeline vi phạm và chỉ train/fine-tune khi baseline/shadow mode không đạt |
| Backend | API, cơ sở dữ liệu, xử lý sự kiện, điểm danh/chấm công, báo cáo, thông báo, audit và quản trị |
| Web Portal | Giao diện phụ huynh, giáo viên/cán bộ, BGH và quản trị viên |
| Mobile App | Một codebase React Native cho iOS/Android, thông báo đẩy và consent |
| Bảo mật | Xác thực, MFA, RBAC, mã hóa, secrets, kiểm thử bảo mật, log và phản ứng sự cố |
| DevOps | Container, CI/CD, môi trường, giám sát, backup, restore, release và rollback |
| QA | Unit, integration, E2E, tải, khả năng phục hồi, UAT và regression |
| Bàn giao | Tài liệu, đào tạo, runbook, bàn giao kỹ thuật, go-live và hỗ trợ |

### 3.2 Ngoài phạm vi

- Khảo sát vị trí lắp camera.
- Mua sắm, lắp đặt, căn chỉnh hoặc bảo trì camera/NVR.
- Đi dây mạng, cấp nguồn, tủ mạng, switch, VLAN vật lý hoặc thi công hạ tầng.
- Cung cấp máy chủ/GPU, thiết bị lưu trữ và đường truyền, trừ khi có phụ lục hợp đồng riêng.
- Tư vấn pháp lý chính thức; đội phát triển chỉ triển khai yêu cầu kỹ thuật sau khi nội dung pháp lý được phê duyệt.
- Trực vận hành 24/7 nếu chưa có hợp đồng SLA riêng.
- Các tích hợp ngoài danh sách đã chốt như hệ thống học vụ, HRM, SMS trả phí hoặc cổng định danh khác.

### 3.3 Nguyên tắc kiểm soát phạm vi

Mọi yêu cầu mới phải được ghi nhận bằng change request, mô tả giá trị, ảnh hưởng kỹ thuật, bảo mật, dữ liệu, chi phí và tiến độ. Không đưa yêu cầu mới trực tiếp vào phiên bản đang kiểm thử nếu chưa có phê duyệt.

## 4. Định hướng kiến trúc và công nghệ

### 4.1 Kiến trúc logic

1. Camera IP/NVR cung cấp luồng RTSP/ONVIF hoặc API đã được bàn giao.
2. ANSVIS hoặc lớp video service nhận luồng, tiền xử lý, chạy model, áp dụng ROI/rule và phát sinh event.
3. Backend tiếp nhận event qua adapter, kiểm tra tính hợp lệ, chống trùng và xử lý nghiệp vụ.
4. Database/object storage lưu dữ liệu theo chính sách retention; dữ liệu nhạy cảm được mã hóa.
5. Web Portal và Mobile App truy cập API theo vai trò.
6. Notification service gửi push/email/SMS tùy phạm vi được phê duyệt.
7. Monitoring/audit ghi nhận tình trạng hệ thống và thao tác nhạy cảm.

### 4.2 Vai trò dự kiến của ANSCENTER

- **ANSVIS:** tiếp nhận video camera IP, thực hiện pipeline AI, rule, event và chuyển kết quả cho backend.
- **ANSTS:** gán nhãn, huấn luyện, đánh giá và xuất model object detection để triển khai lên ANSVIS.
- **Lớp adapter nội bộ:** cô lập backend khỏi API cụ thể của ANSCENTER, giúp đổi version hoặc thay thế thành phần mà không sửa toàn bộ hệ thống.
- **Điểm phải xác minh:** số camera/license; API/webhook; cơ chế xác thực; format event/snapshot; model được hỗ trợ; face recognition; hiệu năng GPU/CPU; cách backup cấu hình/model.

### 4.3 Công nghệ dự kiến

| Thành phần | Định hướng |
|---|---|
| Backend API | Python hoặc Node.js; lựa chọn cuối theo khả năng tích hợp AI/ANSVIS và năng lực vận hành |
| Database | PostgreSQL; Redis cho cache/queue/lock nếu cần |
| AI training/deployment | ANSTS/ANSVIS kết hợp model phù hợp; model và dataset được version hóa |
| Web | Framework web hiện đại hỗ trợ responsive và RBAC |
| Mobile | React Native dùng chung codebase iOS/Android |
| Đóng gói | Docker; Docker Compose hoặc nền tảng orchestration theo quy mô hạ tầng |
| CI/CD | Kiểm tra, scan, build, deploy staging tự động; production cần phê duyệt thủ công |
| Quan sát hệ thống | Centralized log, metric, health check, cảnh báo và audit trail |

Việc khóa framework/phiên bản chỉ thực hiện sau proof-of-concept tích hợp ANSCENTER và đánh giá môi trường triển khai.

## 5. Kế hoạch công việc tổng thể

### 5.1 Nhóm A — Khởi động, phân tích và thiết kế

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| A-01 | Xác định stakeholder, đầu mối ra quyết định và ma trận trách nhiệm | Bắt buộc | RACI và danh sách liên hệ | Không |
| A-02 | Chốt phạm vi 34 camera, khu vực, nghiệp vụ và ngoài phạm vi | Bắt buộc | Scope baseline | A-01 |
| A-03 | Thu thập quy tắc điểm danh, đi trễ, chấm công và xử lý vi phạm | Bắt buộc | Business rule catalogue | A-02 |
| A-04 | Xác định vai trò và quyền dữ liệu của phụ huynh/GV/BGH/admin | Bắt buộc | Access matrix | A-03 |
| A-05 | Xác minh phiên bản, license và API của ANSCENTER | Bắt buộc | Capability/gap matrix | A-04 |
| A-06 | Thiết kế kiến trúc thành phần và luồng dữ liệu | Bắt buộc | Architecture diagram | A-05 |
| A-07 | Thiết kế database, event schema và API contract | Bắt buộc | ERD và API specification | A-06 |
| A-08 | Thiết kế luồng giao diện Web/Mobile | Bắt buộc | Wireflow và screen list | A-07 |
| A-09 | Lập threat model và phân loại dữ liệu | Bắt buộc | Threat register/data inventory | A-08 |
| A-10 | Chốt tiêu chí nghiệm thu và phương pháp đo AI | Bắt buộc | Acceptance baseline | A-09 |
| A-11 | Lập backlog, phụ thuộc và chiến lược release | Bắt buộc | Product backlog/release strategy | A-10 |

### 5.2 Nhóm B — Nền tảng kỹ thuật, DevOps và bảo mật cơ sở

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| B-01 | Khởi tạo repository, branching, coding standard và PR checklist | Bắt buộc | Repository chuẩn hóa | A-11 |
| B-02 | Chuẩn hóa cấu hình dev/staging/production | Bắt buộc | Environment matrix | B-01 |
| B-03 | Đóng gói service/database/cache bằng container | Bắt buộc | Container stack | B-02 |
| B-04 | Thiết lập CI với lint, test, SAST, dependency và secret scan | Bắt buộc | CI pipeline | B-03 |
| B-05 | Thiết lập CD cho staging và quy trình duyệt production | Bắt buộc | Deployment pipeline | B-04 |
| B-06 | Thiết lập secret manager, phân tách secret và rotation | Bắt buộc | Secret management procedure | B-05 |
| B-07 | Thiết lập TLS, domain, reverse proxy/API gateway | Bắt buộc | Kết nối HTTPS an toàn | B-06 |
| B-08 | Thiết lập log tập trung, metric, health check và cảnh báo | Bắt buộc | Monitoring baseline | B-07 |
| B-09 | Thiết lập backup mã hóa và quy trình restore | Bắt buộc | Backup/restore runbook | B-08 |
| B-10 | Thiết lập release version, artifact registry và rollback | Bắt buộc | Release procedure | B-09 |

### 5.3 Nhóm C — Backend và dữ liệu nghiệp vụ

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| C-01 | Xây schema và migration cho user, student, staff, camera, event | Bắt buộc | Database schema | B-10 |
| C-02 | Xây authentication, reset password, session và revoke token | Bắt buộc | Authentication API | C-01 |
| C-03 | Xây MFA cho Admin/BGH và RBAC tại API | Bắt buộc | Authorization service | C-02 |
| C-04 | Xây API quản lý người dùng, học sinh, cán bộ và liên kết phụ huynh | Bắt buộc | Master-data API | C-03 |
| C-05 | Xây API danh mục camera, khu vực, pipeline và trạng thái | Bắt buộc | Camera registry API | C-04 |
| C-06 | Xây adapter nhận event từ ANSVIS/API ngoài | Bắt buộc | Event ingestion adapter | C-05 |
| C-07 | Kiểm tra schema, chống event trùng/replay và xử lý retry | Bắt buộc | Reliable ingestion flow | C-06 |
| C-08 | Xây rule nghiệp vụ điểm danh, đi trễ và chấm công | Bắt buộc | Attendance/timekeeping service | C-07 |
| C-09 | Xây quản lý vi phạm, review, xác nhận sai và chỉnh sửa | Bắt buộc | Violation workflow | C-08 |
| C-10 | Xây consent, rút consent và yêu cầu sửa/xóa dữ liệu | Bắt buộc | Privacy workflow | C-09 |
| C-11 | Xây notification service và quản lý device token | Bắt buộc | Notification API | C-10 |
| C-12 | Xây báo cáo, thống kê và xuất Excel/PDF an toàn | Bắt buộc | Reporting service | C-11 |
| C-13 | Xây audit log cho hành động nhạy cảm | Bắt buộc | Audit trail | C-12 |
| C-14 | Xây retention job và cơ chế xóa/ẩn danh dữ liệu | Bắt buộc | Data lifecycle automation | C-13 |

### 5.4 Nhóm D — AI điểm danh và chấm công

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| D-01 | Xác định quy chuẩn dataset và nguồn dữ liệu có consent | Bắt buộc | Dataset specification | C-14 |
| D-02 | Xây quy trình enrollment có kiểm tra consent | Bắt buộc | Enrollment workflow | D-01 |
| D-03 | Tiền xử lý ảnh, quality gate và phát hiện khuôn mặt | Bắt buộc | Face quality pipeline | D-02 |
| D-04 | Tạo, mã hóa và quản lý vòng đời face embedding | Bắt buộc | Encrypted embedding store | D-03 |
| D-05 | Cấu hình/tích hợp Facial Recognition có sẵn và unknown handling | Bắt buộc | Versioned recognition config | D-04 |
| D-06 | Hiệu chỉnh threshold theo FAR/FRR và điều kiện quan sát | Bắt buộc | Threshold report | D-05 |
| D-07 | Tích hợp nhận diện với logic điểm danh/chấm công | Bắt buộc | Attendance AI flow | D-06 |
| D-08 | Xây cơ chế chống ghi nhận trùng và manual correction | Bắt buộc | Reconciliation workflow | D-07 |
| D-09 | Ghi nhận happiness index vào Future Scope; không triển khai trong baseline | Tùy chọn | Change request riêng nếu phát sinh | Không chặn baseline |
| D-10 | Kiểm tra bias, sai số, độ trễ và giới hạn sử dụng | Bắt buộc | AI evaluation/model card | D-09 |
| D-11 | Chạy shadow mode và quy trình rollback model | Bắt buộc | Shadow-test report | D-10 |

### 5.5 Nhóm E — AI phát hiện vi phạm

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| E-01 | Viết spec 4 pipeline: đồng phục, PPE bếp, xả rác, hút thuốc | Bắt buộc | Pipeline spec | D-11 |
| E-02 | Kiểm model hiện có và khả năng baseline trong ANSVIS | Bắt buộc | Capability/baseline matrix | E-01 |
| E-03 | Cấu hình ROI, threshold, presence time, tracker/rule cho từng pipeline | Bắt buộc | Rule configuration | E-02 |
| E-04 | Chạy shadow mode từng pipeline, chưa tự động kết luận nhạy cảm | Bắt buộc | Shadow report | E-03 |
| E-05 | Đo precision, recall, false positive/false negative, latency và false-alert rate | Bắt buộc | Evaluation report | E-04 |
| E-06 | Xây guideline dataset/label/sanitization nếu pipeline không đạt | Có điều kiện | Labelling/data guide | E-05 |
| E-07 | Train/fine-tune/import model cho pipeline chưa đạt nếu cần | Có điều kiện | Model artifact/model card | E-06 |
| E-08 | Version model/config, checksum, approval và rollback từng pipeline | Bắt buộc | Model/config registry | E-07 hoặc E-05 |
| E-09 | Xây debounce/grouping để giảm cảnh báo trùng | Bắt buộc | Event filtering logic | E-08 |
| E-10 | Bảo vệ webhook/event và kiểm soát snapshot | Bắt buộc | Secured event channel | E-09 |
| E-11 | Chốt human review/appeal cho event nhạy cảm | Bắt buộc | Review workflow | E-10 |
| E-12 | Nghiệm thu từng pipeline trước production | Bắt buộc | Pipeline acceptance report | E-11 |

### 5.6 Nhóm F — Web Portal

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| F-01 | Khởi tạo web, design system, routing và responsive layout | Bắt buộc | Web foundation | Backend/API contract + mock event |
| F-02 | Xây login, MFA, session timeout và error handling | Bắt buộc | Secure authentication UI | F-01 |
| F-03 | Xây giao diện phụ huynh xem điểm danh và vi phạm của con | Bắt buộc | Parent portal | F-02 |
| F-04 | Xây giao diện giáo viên/cán bộ xem chấm công | Bắt buộc | Staff portal | F-03 |
| F-05 | Xây dashboard BGH và biểu đồ xu hướng | Bắt buộc | Management dashboard | F-04 |
| F-06 | Xây màn hình review/override cảnh báo AI | Bắt buộc | Human-review interface | F-05 |
| F-07 | Xây màn hình báo cáo và xuất dữ liệu | Bắt buộc | Reporting interface | F-06 |
| F-08 | Xây màn hình quản trị user, role và liên kết phụ huynh | Bắt buộc | Administration UI | F-07 |
| F-09 | Xây giao diện consent và yêu cầu quyền dữ liệu | Bắt buộc | Privacy interface | F-08 |
| F-10 | Áp dụng CSP, security headers, chống XSS/CSRF/IDOR | Bắt buộc | Hardened web release | F-09 |
| F-11 | Kiểm thử responsive, browser và accessibility cơ bản | Bắt buộc | Web QA report | F-10 |

### 5.7 Nhóm G — Mobile App React Native

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| G-01 | Khởi tạo codebase, cấu hình iOS/Android và build pipeline | Bắt buộc | Mobile foundation | F-11 |
| G-02 | Xây navigation, API client và quản lý lỗi/mất mạng | Bắt buộc | App framework | G-01 |
| G-03 | Xây login, MFA, refresh/revoke và logout | Bắt buộc | Mobile authentication | G-02 |
| G-04 | Lưu token bằng Keychain/Keystore | Bắt buộc | Secure storage | G-03 |
| G-05 | Cấu hình certificate validation/pinning và rotation | Bắt buộc | Protected API channel | G-04 |
| G-06 | Xây màn hình điểm danh/chấm công | Bắt buộc | Attendance screens | G-05 |
| G-07 | Xây màn hình vi phạm và phản hồi cảnh báo sai | Bắt buộc | Violation screens | G-06 |
| G-08 | Xây push notification, deep link và device-token revoke | Bắt buộc | Push workflow | G-07 |
| G-09 | Xây consent, rút consent và yêu cầu dữ liệu | Bắt buộc | Mobile privacy flow | G-08 |
| G-10 | Hardening production build, bỏ debug log và obfuscation phù hợp | Bắt buộc | Hardened app build | G-09 |
| G-11 | Test thiết bị/hệ điều hành mục tiêu | Bắt buộc | Device test report | G-10 |
| G-12 | Chuẩn bị privacy label, listing và hồ sơ App Store/Google Play | Bắt buộc | Store submission package | G-11 |

### 5.8 Nhóm H — Tích hợp 34 camera và kiểm thử toàn hệ thống

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| H-01 | Nhận và kiểm tra phiếu bàn giao luồng/API từng camera | Bắt buộc | Camera connection matrix | G-12 + đầu vào camera |
| H-02 | Đưa credential vào secret manager, không ghi trong source/ticket | Bắt buộc | Secured credentials | H-01 |
| H-03 | Ánh xạ camera–khu vực–model–ROI–rule | Bắt buộc | Approved mapping | H-02 |
| H-04 | Kiểm tra kết nối, time sync, reconnect và chất lượng luồng | Bắt buộc | Stream health report | H-03 |
| H-05 | Kiểm thử camera → ANSVIS → backend → web/app → thông báo | Bắt buộc | E2E report | H-04 |
| H-06 | Kiểm thử event trùng, mất luồng, timeout và dữ liệu sai | Bắt buộc | Failure-case report | H-05 |
| H-07 | Chạy shadow mode và hiệu chỉnh model/rule | Bắt buộc | Calibration report | H-06 |
| H-08 | Kiểm thử tải với số luồng/event mục tiêu | Bắt buộc | Capacity report | H-07 |
| H-09 | Kiểm thử quyền truy cập chéo giữa các vai trò | Bắt buộc | Authorization test report | H-08 |
| H-10 | Kiểm thử backup/restore, restart và rollback | Bắt buộc | Recovery test report | H-09 |
| H-11 | Tổ chức UAT và quản lý lỗi theo mức độ | Bắt buộc | UAT record | H-10 |
| H-12 | Regression sau sửa lỗi và khóa release candidate | Bắt buộc | Approved release candidate | H-11 |

### 5.9 Nhóm I — Bảo mật chuyên sâu và sẵn sàng go-live

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| I-01 | Cập nhật threat model theo hệ thống đã triển khai | Bắt buộc | Final threat model | H-12 |
| I-02 | Review OWASP Top 10 cho backend/web/API | Bắt buộc | Secure-code review report | I-01 |
| I-03 | Review mobile storage, network, log và production build | Bắt buộc | Mobile security report | I-02 |
| I-04 | Quét dependency, container, secret, SAST và DAST | Bắt buộc | Vulnerability scan report | I-03 |
| I-05 | Pentest cơ bản login, RBAC/IDOR, injection, upload và webhook | Bắt buộc | Pentest report | I-04 |
| I-06 | Rà soát mã hóa database, object storage, backup và embedding | Bắt buộc | Encryption checklist | I-05 |
| I-07 | Rà retention, consent, rút consent và quyền xóa dữ liệu | Bắt buộc | Privacy compliance evidence | I-06 |
| I-08 | Rà log để loại token, secret và dữ liệu nhạy cảm không cần thiết | Bắt buộc | Logging review | I-07 |
| I-09 | Xây và diễn tập Incident Response Plan | Bắt buộc | Incident drill record | I-08 |
| I-10 | Đóng lỗi Critical/High hoặc có phê duyệt rủi ro chính thức | Bắt buộc | Security sign-off | I-09 |

### 5.10 Nhóm J — Triển khai, đào tạo và bàn giao

| ID | Công việc | Ưu tiên | Đầu ra | Phụ thuộc |
|---|---|---|---|---|
| J-01 | Chuẩn bị release note, deployment plan và rollback plan | Bắt buộc | Go-live package | I-10 |
| J-02 | Backup trước release và triển khai production có phê duyệt | Bắt buộc | Production release | J-01 |
| J-03 | Chạy smoke test và theo dõi log/metric sau triển khai | Bắt buộc | Go-live verification | J-02 |
| J-04 | Submit/phát hành ứng dụng trên hai store | Bắt buộc | Store release/submission | J-03 |
| J-05 | Soạn hướng dẫn phụ huynh, giáo viên, BGH và admin | Bắt buộc | User manuals | J-04 |
| J-06 | Soạn runbook triển khai, monitoring, backup và incident | Bắt buộc | Technical runbook | J-05 |
| J-07 | Đào tạo người dùng theo vai trò bằng dữ liệu demo | Bắt buộc | Training records | J-06 |
| J-08 | Bàn giao source/artifact/model/config theo hợp đồng | Bắt buộc | Technical handover | J-07 |
| J-09 | Chuyển quyền tài khoản/secrets bằng kênh an toàn và bật MFA | Bắt buộc | Ownership handover | J-08 |
| J-10 | Chốt SLA, đầu mối hỗ trợ và escalation | Bắt buộc | Support agreement | J-09 |
| J-11 | Thực hiện hyper-care và tổng hợp vấn đề sau go-live | Sau go-live | Hyper-care report | J-10 |
| J-12 | Review chất lượng AI, false alerts và backlog cải tiến | Sau go-live | Operational review | J-11 |

## 6. Bộ tài liệu thiết kế cần bổ sung

Phần này bổ sung danh mục tài liệu thiết kế cần chuẩn bị để Ban lãnh đạo, khách hàng và đội triển khai có cùng cách hiểu trước khi phát triển chi tiết. Các tài liệu bên dưới chỉ mô tả phần mềm, dữ liệu, AI, tích hợp ANSVIS/backend/web/mobile, bảo mật, kiểm thử và vận hành. Không đưa khảo sát hiện trường, mua/lắp camera, kéo dây, cấp nguồn hoặc thi công mạng vật lý vào phạm vi thực hiện của đội phát triển.

| STT | Mức ưu tiên | Tài liệu cần bổ sung | Mục đích | Nội dung cần có | Đầu ra bàn giao | Liên hệ với kế hoạch hiện tại |
|---|---|---|---|---|---|---|
| 1 | Rất cao | Software Requirement Specification (SRS) | Mô tả đầy đủ yêu cầu phần mềm để tránh hiểu sai giữa Ban lãnh đạo, khách hàng và người phát triển | Phạm vi phần mềm; vai trò người dùng; chức năng điểm danh, chấm công, vi phạm, thông báo, báo cáo, consent; yêu cầu phi chức năng về bảo mật, hiệu năng, lưu trữ, backup, audit; ngoài phạm vi phần cứng | Tài liệu SRS có version, được duyệt làm baseline yêu cầu | A-02, A-03, A-04, A-09, A-10 |
| 2 | Rất cao | Use Case | Xác định từng vai trò được phép làm gì trong hệ thống | Use case cho Phụ huynh, Giáo viên/Cán bộ, Ban giám hiệu, Admin, hệ thống ANSVIS/backend; quyền xem/sửa/xác nhận/xuất báo cáo; ràng buộc RBAC và quyền dữ liệu theo từng học sinh/cán bộ | Use case catalogue và access matrix | A-04, C-03, F-03 đến F-09, G-06 đến G-09 |
| 3 | Rất cao | Business Flow / Quy trình nghiệp vụ | Làm rõ luồng xử lý nghiệp vụ trước khi code để tránh sai logic vận hành | Quy trình điểm danh học sinh; chấm công cán bộ; xử lý đi trễ; xử lý vi phạm đồng phục/xả rác/hút thuốc/bảo hộ bếp; human review; chỉnh sửa thủ công; thông báo; rút consent; xóa dữ liệu | Bộ sơ đồ/quy trình nghiệp vụ được duyệt | A-03, C-08, C-09, C-10, D-07, E-09 |
| 4 | Rất cao | Event Flow | Mô tả đường đi của dữ liệu từ camera đến màn hình và thông báo | Luồng Camera/NVR/RTSP hoặc API đã bàn giao → ANSVIS/video service → backend adapter → database/object storage → notification → dashboard/web/mobile; xử lý event trùng, retry, timeout, mất luồng, sai schema; bảo vệ webhook và snapshot | Event flow diagram và event handling rule | A-06, C-06, C-07, E-10, H-05, H-06 |
| 5 | Rất cao | Database Design (ERD) | Thiết kế toàn bộ bảng dữ liệu, quan hệ và chính sách lưu trữ trước khi phát triển backend | Bảng user, role, student, staff, guardian, camera, area, model, pipeline, event, attendance, violation, consent, notification, audit log, retention, device token; khóa chính/khóa ngoại; index; partition nếu cần; dữ liệu mã hóa | ERD, data dictionary và migration baseline | A-07, C-01, C-13, C-14, I-06 |
| 6 | Rất cao | API Specification (Swagger/OpenAPI) | Chuẩn hóa giao tiếp giữa backend, web, mobile và ANSVIS/adapter | API authentication, user/student/staff, camera registry, event ingestion, attendance, violation, notification, report, consent, admin; request/response mẫu; mã lỗi; phân quyền; rate limit; webhook/event payload từ ANSVIS | OpenAPI/Swagger file và API contract | A-07, C-02 đến C-12, F/G tích hợp API |
| 7 | Cao | UI Sitemap & Wireframe | Xác định danh sách màn hình và cách điều hướng trước khi làm giao diện | Sitemap Web Portal và Mobile App; màn hình đăng nhập/MFA; dashboard BGH; điểm danh; chấm công; vi phạm; báo cáo; quản trị user/role; consent; thông báo; trạng thái lỗi/mất mạng | Sitemap, wireframe low-fidelity và screen list | A-08, F-01 đến F-11, G-01 đến G-12 |
| 8 | Cao | Sequence Diagram | Mô tả trình tự xử lý cho các chức năng chính để dev kiểm tra phụ thuộc và lỗi biên | Sequence đăng nhập/MFA; enrollment khuôn mặt; điểm danh tự động; phát hiện vi phạm; gửi thông báo; giáo viên/BGH xác nhận cảnh báo; rút consent; xuất báo cáo; backup/restore; incident response | Bộ sequence diagram cho luồng chính và luồng lỗi | A-06, C-06 đến C-12, D-02, D-07, H-05 |
| 9 | Cao | Deployment Architecture | Mô tả cách triển khai thực tế trên server/môi trường vận hành | Sơ đồ service backend, database, Redis, object storage, ANSVIS/video service, web, mobile API, reverse proxy/API gateway, TLS, monitoring, backup, staging/production, rollback; phân vùng trách nhiệm phần mềm và hạ tầng được bàn giao | Deployment architecture diagram và environment matrix | B-02, B-03, B-07, B-08, B-09, J-01 |
| 10 | Cao | Hạ tầng & Performance | Ước tính tài nguyên và ngưỡng vận hành để tránh thiếu CPU/GPU/storage/network | Ước tính số luồng camera, FPS/resolution mục tiêu, số event/ngày, lưu snapshot/video, dung lượng database/object storage, CPU/GPU/RAM, network, backup window, log retention, benchmark 34 camera, ngưỡng cảnh báo | Capacity/performance plan và benchmark checklist | A-05, B-08, H-08, J-03 |
| 11 | Trung bình | Risk Register | Theo dõi rủi ro và phương án xử lý theo ngôn ngữ dễ hiểu cho quản lý | Rủi ro ANSCENTER/license/API; dữ liệu training không đủ; AI sai số cao; chậm bàn giao luồng camera; rò rỉ dữ liệu sinh trắc học; thiếu nhân lực; store review mobile; hiệu năng 34 camera; thay đổi yêu cầu; mất dữ liệu/backup lỗi | Risk register có chủ sở hữu, mức ảnh hưởng và phương án giảm thiểu | QĐ-02 đến QĐ-07, A-09, I-09 |
| 12 | Trung bình | Timeline / Sprint Plan | Làm căn cứ đàm phán tiến độ sau khi chốt phạm vi và nguồn lực | Chia giai đoạn theo nhóm A-J; thứ tự tuần tự do 01 developer thực hiện; phụ thuộc đầu vào từ khách hàng/đơn vị thi công; milestone demo/UAT/go-live/bàn giao; chưa khóa ngày cụ thể cho đến khi đàm phán | Sprint/release plan dạng tương đối, không cam kết ngày | 5.1 đến 5.10, 7.1, 7.2 |
| 13 | Trung bình | Test Plan | Xác định cách kiểm thử trước khi nghiệm thu và go-live | Unit test; integration test; E2E camera → ANSVIS → backend → web/mobile → notification; AI test; security test; mobile device test; backup/restore test; UAT; regression; dữ liệu test và tiêu chí pass/fail | Test plan, test case matrix và test report template | H-05 đến H-12, I-02 đến I-05, J-03 |
| 14 | Trung bình | Acceptance Criteria | Làm rõ tiêu chí nghiệm thu từng module để khách hàng xác nhận hoàn thành | Tiêu chí cho backend, AI điểm danh, AI vi phạm, Web Portal, Mobile App, báo cáo, thông báo, consent, bảo mật, backup/restore, vận hành; quy định lỗi blocker/critical; tiêu chí AI dựa trên dataset đã duyệt | Acceptance criteria checklist theo module/milestone | A-10, H-11, H-12, J-08 |
| 15 | Thấp | Vận hành & Bảo trì (SOP/Runbook) | Hướng dẫn vận hành sau bàn giao để giảm phụ thuộc cá nhân phát triển | Quy trình deploy, rollback, backup, restore, monitoring, kiểm tra camera/API, xử lý mất luồng, restart service, rotate secrets, xử lý incident bảo mật, support ticket, SLA, escalation, cập nhật model/rule | SOP/runbook vận hành và tài liệu bàn giao kỹ thuật | B-09, B-10, I-09, J-05, J-06, J-10 |

### 6.1 Thứ tự ưu tiên soạn tài liệu

Để phục vụ quyết định của Ban lãnh đạo và giảm rủi ro hiểu sai, các tài liệu nên được làm theo thứ tự:

1. SRS, Use Case, Business Flow, Event Flow.
2. Database Design, API Specification, Deployment Architecture.
3. UI Sitemap/Wireframe, Sequence Diagram, Test Plan, Acceptance Criteria.
4. Hạ tầng & Performance, Risk Register, Timeline/Sprint Plan.
5. SOP/Runbook hoàn thiện dần trong quá trình triển khai và khóa trước bàn giao.

Các mục “Rất cao” phải được chốt trước khi phát triển sâu backend/AI/web/mobile. Các mục “Cao” nên có bản nháp trước khi bắt đầu implementation tương ứng. Các mục “Trung bình/Thấp” có thể cập nhật lặp lại theo tiến độ đàm phán và triển khai, nhưng phải có bản cuối trước UAT/go-live.

## 7. Thứ tự ưu tiên và phụ thuộc chính

### 7.1 Chuỗi công việc bắt buộc

`Yêu cầu → xác minh ANSCENTER → kiến trúc/bảo mật → nền tảng → backend → AI → web → mobile → tích hợp camera → E2E/security/UAT → go-live → bàn giao`

Với một developer, đây là chuỗi thực hiện chính. Một số hoạt động nhỏ có thể xen kẽ trong thời gian chờ phản hồi hoặc chờ store review, nhưng không được coi là hai luồng phát triển độc lập.

### 7.2 Các cổng quyết định

| Gate | Điều kiện để đi tiếp |
|---|---|
| G0 – Chấp thuận phạm vi | Scope, vai trò, ngoài phạm vi và đầu mối phê duyệt rõ ràng |
| G1 – Khả thi kỹ thuật | ANSCENTER/license/API, hạ tầng và luồng mẫu đáp ứng hoặc có phương án thay thế |
| G2 – Cho phép dùng dữ liệu thật | Consent/chính sách dữ liệu được phê duyệt; secret và mã hóa sẵn sàng |
| G3 – Chấp thuận AI | Dataset/test protocol hợp lệ; model đạt ngưỡng thử nghiệm; giới hạn được công bố |
| G4 – Chấp thuận UAT | Luồng E2E đạt; blocker/critical bằng 0; lỗi còn lại có kế hoạch được duyệt |
| G5 – Chấp thuận go-live | Backup/rollback/incident plan đã thử; security sign-off; người vận hành sẵn sàng |
| G6 – Nghiệm thu | Tài liệu, đào tạo, tài sản bàn giao và SLA đầy đủ |

## 8. Tiêu chuẩn hoàn thành chung

Một hạng mục chỉ được coi là hoàn thành khi:

- Yêu cầu và tiêu chí chấp nhận đã rõ.
- Mã nguồn/cấu hình/model có version và nằm trong hệ thống quản lý phù hợp.
- Có unit/integration/E2E test tương ứng với mức rủi ro.
- CI không còn lỗi; không còn secret trong source/artifact/log.
- Tài liệu API, cấu hình, release note và runbook liên quan đã cập nhật.
- Bảo mật/RBAC/retention/consent được kiểm tra nếu hạng mục xử lý dữ liệu cá nhân.
- Đã deploy lên staging và có bằng chứng kiểm thử.
- Lỗi blocker/critical đã đóng.
- Người có thẩm quyền phê duyệt nếu đây là milestone hoặc thay đổi rủi ro cao.

## 9. Chỉ tiêu chất lượng đề xuất

| Nhóm | Chỉ tiêu/Nguyên tắc |
|---|---|
| AI detection | Đo precision, recall, F1, mAP và false alerts/camera/giờ trên tập test độc lập |
| Face recognition | Đo FAR/FRR theo threshold và điều kiện quan sát; có trạng thái unknown/human review |
| Hiệu năng | Đo độ trễ event đến giao diện, tài nguyên CPU/GPU/RAM, queue backlog và sức chứa storage |
| Khả dụng | Tự reconnect, health check, cảnh báo, backup/restore và rollback được kiểm chứng |
| Bảo mật | Không còn lỗ hổng Critical/High trước go-live; MFA Admin/BGH; RBAC/API test đầy đủ |
| Quyền riêng tư | Consent trước enrollment; mã hóa; retention/xóa; phụ huynh chỉ xem dữ liệu con mình |
| Mobile | Không lưu token plaintext; production build không để debug secret/log; test iOS/Android mục tiêu |
| Nghiệp vụ | Báo cáo đối soát đúng database; chỉnh sửa thủ công có audit; cảnh báo AI có human review |

Ngưỡng số cụ thể được chốt trong phụ lục nghiệm thu sau khi có dataset, phần cứng và luồng camera đại diện.

## 10. Kế hoạch triển khai kiểm soát chất lượng

Vì thời gian triển khai không phải ràng buộc chính, dự án nên đi theo hướng kiểm soát chất lượng theo từng lớp, không đẩy nhanh bằng cách bỏ qua tài liệu, kiểm thử, bảo mật hoặc shadow mode. Mục tiêu là khi đưa dịch vụ tới khách hàng, hệ thống có thể vận hành ổn định, có bằng chứng kiểm thử, có quy trình xử lý sự cố và có giới hạn trách nhiệm rõ ràng.

### 10.1 Nguyên tắc triển khai

| Nguyên tắc | Cách áp dụng |
|---|---|
| Làm đúng trước khi làm nhanh | Không chuyển phase nếu chưa đạt exit criteria và quality gate |
| Chia nhỏ để kiểm soát rủi ro | Mỗi module phải có tài liệu, test case, dữ liệu mẫu, log/audit và tiêu chí nghiệm thu riêng |
| Không dùng dữ liệu thật khi chưa sẵn sàng | Chỉ dùng dữ liệu thật sau khi consent, mã hóa, RBAC, audit và retention đã được kiểm tra |
| AI phải có human review | Kết quả AI trong giai đoạn đầu là đề xuất/cảnh báo, không dùng tự động để kết luận kỷ luật |
| Bảo mật đi cùng từng hạng mục | Mỗi module có checklist bảo mật riêng: auth, RBAC, input validation, log, mã hóa, phân quyền dữ liệu |
| Mọi thay đổi có dấu vết | Code, config, model, dataset, API contract, release note và quyết định nghiệm thu phải được version hóa |
| Không go-live nếu chưa có rollback | Trước production phải có backup, restore test, rollback plan và người chịu trách nhiệm xác nhận |

### 10.2 Mô hình triển khai đề xuất

| Lớp triển khai | Mục tiêu | Điều kiện hoàn thành |
|---|---|---|
| Lớp 1 — Tài liệu nền | Chốt đúng yêu cầu, quyền, dữ liệu, API, kiến trúc và tiêu chí nghiệm thu | SRS, use case, business flow, event flow, ERD, API spec, test plan và acceptance criteria được duyệt |
| Lớp 2 — Nền tảng kỹ thuật | Tạo môi trường phát triển an toàn, có CI/CD, secret, log, backup | Dev/staging hoạt động; secret không hard-code; CI có lint/test/security scan; backup/restore thử thành công |
| Lớp 3 — Backend core | Có API, database, RBAC, event ingestion, audit, notification và report cơ bản | API test đạt; RBAC test đạt; event từ ANSVIS được nhận, chống trùng và ghi audit |
| Lớp 4 — AI core | Huấn luyện/tích hợp model, cấu hình pipeline/rule và đo sai số | Có model card; có threshold report; có shadow-test report; có rollback model |
| Lớp 5 — Web/Mobile | Người dùng truy cập đúng vai trò, thao tác được nghiệp vụ chính | UI test, API integration test, mobile device test và security checklist đạt |
| Lớp 6 — Tích hợp toàn hệ thống | Kiểm tra luồng camera/event/thông báo/báo cáo end-to-end | E2E test đạt với camera đại diện; sau đó mở rộng dần đến 34 camera |
| Lớp 7 — UAT và go-live | Khách hàng kiểm thử nghiệp vụ thật, hệ thống sẵn sàng vận hành | UAT pass; không còn lỗi blocker/critical; security sign-off; runbook và đào tạo hoàn tất |

## 11. Quality Gate bắt buộc trước khi chuyển giai đoạn

Quality Gate là điểm kiểm soát bắt buộc. Nếu không đạt, không chuyển sang giai đoạn tiếp theo, trừ khi Ban lãnh đạo và khách hàng chấp nhận rủi ro bằng văn bản.

| Gate | Thời điểm kiểm soát | Checklist bắt buộc | Bằng chứng cần có |
|---|---|---|---|
| QG-01 — Scope & Requirement Gate | Trước khi phát triển sâu | SRS đã duyệt; use case đủ vai trò; business flow rõ; ngoài phạm vi phần cứng được ghi rõ; acceptance criteria bản đầu đã có | SRS, use case catalogue, business flow, acceptance baseline |
| QG-02 — Architecture & Data Gate | Trước khi xây backend chính | ERD, API spec, event flow, deployment architecture, data classification, retention policy và threat model đã có | ERD, OpenAPI, event schema, architecture diagram, threat register |
| QG-03 — Platform Gate | Trước khi tích hợp dữ liệu thật | CI/CD, secret manager, TLS, logging, backup, restore, RBAC foundation, staging environment đã hoạt động | CI report, secret checklist, restore evidence, staging URL, access matrix |
| QG-04 — Backend Gate | Trước khi làm UI tích hợp sâu | API chính ổn định; auth/MFA/RBAC hoạt động; event ingestion chống trùng; audit log; notification; report cơ bản | API test report, RBAC test report, event replay test, audit evidence |
| QG-05 — AI Gate | Trước khi bật AI cho người dùng thật | Dataset hợp lệ; model card; threshold; false-positive/false-negative report; shadow mode; rollback model | AI evaluation report, model version, shadow-test log, rollback checklist |
| QG-06 — Web/Mobile Gate | Trước khi UAT | UI đủ luồng chính; không lộ dữ liệu chéo; mobile token an toàn; push notification test; lỗi UX nghiêm trọng đã đóng | UI test report, device test report, RBAC evidence, push test evidence |
| QG-07 — Security & Privacy Gate | Trước go-live | Không còn Critical/High; pentest cơ bản; dependency/container/secret scan; consent/withdraw/delete flow; log không chứa dữ liệu nhạy cảm thừa | Scan report, pentest report, privacy checklist, logging review |
| QG-08 — Operation Gate | Trước nghiệm thu | Backup/restore pass; monitoring/alert pass; runbook có đủ; đào tạo hoàn tất; SLA/support channel rõ | Runbook, training record, smoke test, rollback drill, support matrix |

## 12. Chiến lược đảm bảo chất lượng hệ thống

### 12.1 Kiểm thử phần mềm

| Loại kiểm thử | Phạm vi | Mục tiêu chất lượng |
|---|---|---|
| Unit test | Hàm nghiệp vụ, rule điểm danh, rule chấm công, xử lý event, permission helper | Đảm bảo logic nhỏ đúng và dễ phát hiện lỗi khi sửa |
| Integration test | API + database + queue/cache + object storage + notification | Đảm bảo các service giao tiếp đúng, transaction và retry hoạt động |
| Contract test | Backend với Web/Mobile và ANSVIS adapter | Đảm bảo request/response không bị lệch khi thay đổi API |
| E2E test | Camera/ANSVIS → backend → database → web/mobile → notification | Đảm bảo luồng nghiệp vụ thật chạy được từ đầu đến cuối |
| Regression test | Các lỗi đã sửa, luồng chính trước mỗi release | Không để lỗi cũ quay lại |
| Load/performance test | Event ingestion, dashboard, report, notification, lưu snapshot | Đánh giá khả năng chịu tải khi mở rộng đến 34 camera |
| Recovery test | Restart service, mất database tạm thời, mất luồng camera, restore backup, rollback release | Đảm bảo hệ thống phục hồi được sau sự cố |

### 12.2 Kiểm thử bảo mật và riêng tư

| Nhóm kiểm thử | Nội dung bắt buộc |
|---|---|
| Authentication | Login, reset password, MFA Admin/BGH, revoke token, session timeout |
| Authorization/RBAC | Phụ huynh chỉ xem dữ liệu con mình; giáo viên/BGH/Admin đúng phạm vi; chặn IDOR |
| API Security | Injection, rate limit, input validation, webhook signature/token, lỗi không lộ stack trace |
| Data Protection | Mã hóa dữ liệu nhạy cảm, backup mã hóa, không log token/secret/embedding/snapshot không cần thiết |
| Mobile Security | Token trong Keychain/Keystore, production build bỏ debug log, certificate validation/pinning nếu áp dụng |
| Web Security | CSP, security headers, CSRF/XSS, file export an toàn, kiểm soát quyền tải ảnh/báo cáo |
| Privacy | Consent trước enrollment, rút consent, xóa/ẩn danh dữ liệu, retention job, audit thao tác nhạy cảm |

### 12.3 Kiểm thử AI

| Hạng mục | Cách kiểm soát |
|---|---|
| Dataset | Có guideline gán nhãn, dữ liệu train/validation/test tách riêng, kiểm soát consent và ẩn danh khi không cần nhận diện |
| Face recognition | Đo FAR/FRR theo điều kiện ánh sáng/góc camera; có ngưỡng unknown; không tự động kết luận nếu confidence thấp |
| Object/behavior detection | Đo precision, recall, F1, mAP, false alert rate theo từng loại vi phạm |
| Threshold | Mỗi model có threshold report; thay đổi threshold phải có lý do và log version |
| Shadow mode | Chạy thử không tác động người dùng thật để thu sai số trước khi bật cảnh báo chính thức |
| Human review | Cảnh báo quan trọng phải có người xác nhận, có cơ chế đánh dấu AI sai và dùng dữ liệu đó để cải tiến |
| Model rollback | Mỗi model có version/checksum/model card và cách quay lại version trước |

## 13. Kế hoạch triển khai theo nhịp kiểm soát

Vì không cần khóa ngày ngay, tiến độ nên quản lý bằng trạng thái hoàn thành và bằng chứng chất lượng thay vì ép mốc thời gian. Mỗi nhịp dưới đây chỉ kết thúc khi có đủ tài liệu, test report và sign-off tương ứng.

| Nhịp | Trọng tâm | Công việc chính | Điều kiện kết thúc |
|---|---|---|---|
| Nhịp 1 | Chốt nền yêu cầu | SRS, use case, business flow, event flow, ERD, API spec, acceptance criteria, risk register | QG-01 và QG-02 đạt |
| Nhịp 2 | Dựng nền kỹ thuật | Repository, CI/CD, dev/staging, secret manager, TLS, monitoring, backup/restore, coding/security checklist | QG-03 đạt |
| Nhịp 3 | Backend core | Auth/MFA/RBAC, master data, camera registry, event ingestion, audit, notification, report, consent | QG-04 đạt |
| Nhịp 4 | AI và ANSVIS | POC ANSVIS/API, import model, face recognition, vi phạm, ROI/rule, threshold, model card, shadow mode | QG-05 đạt |
| Nhịp 5 | Web Portal | Parent/staff/BGH/admin portal, dashboard, review violation, report, consent, hardening web | Web test và security checklist web đạt |
| Nhịp 6 | Mobile App | React Native iOS/Android, login/MFA, attendance/violation, consent, push notification, secure storage | Mobile device test và security checklist mobile đạt |
| Nhịp 7 | Tích hợp hệ thống | E2E camera/event/web/mobile/notification, mở rộng dần camera, performance, recovery, regression | QG-06 và phần kỹ thuật QG-08 đạt |
| Nhịp 8 | UAT và hardening | UAT, sửa lỗi, security scan/pentest, privacy review, runbook, training, go-live drill | QG-07 và QG-08 đạt |
| Nhịp 9 | Go-live có kiểm soát | Production release, smoke test, monitoring, hyper-care, review false alerts, backlog cải tiến | Nghiệm thu vận hành và báo cáo sau go-live |

## 14. Chỉ số chất lượng cần theo dõi khi vận hành

Sau go-live, hệ thống không chỉ được đánh giá bằng việc “chạy được”, mà phải theo dõi các chỉ số vận hành để phát hiện sớm suy giảm chất lượng.

| Nhóm chỉ số | Chỉ số cần theo dõi | Mục đích |
|---|---|---|
| Độ ổn định camera/event | Tỷ lệ camera online, số lần mất luồng, thời gian reconnect, số event bị retry/fail | Phát hiện vấn đề luồng/API/cấu hình ANSVIS |
| Hiệu năng | Độ trễ từ event đến dashboard/app, CPU/GPU/RAM, queue backlog, thời gian xuất báo cáo | Đảm bảo hệ thống chịu được tải thực tế |
| AI quality | False alert rate, missed detection, confidence distribution, số cảnh báo bị người dùng đánh dấu sai | Hiệu chỉnh threshold/model theo dữ liệu thật |
| Dữ liệu | Tăng trưởng database/storage, dung lượng snapshot/video, job retention, backup size | Tránh đầy ổ, chậm query, mất kiểm soát chi phí lưu trữ |
| Bảo mật | Login fail bất thường, token revoke, thao tác admin, truy cập dữ liệu nhạy cảm, scan định kỳ | Phát hiện lạm dụng hoặc sự cố bảo mật |
| Nghiệp vụ | Tỷ lệ điểm danh cần chỉnh tay, số vi phạm được xác nhận/sai, thời gian xử lý cảnh báo | Đo mức hữu ích thực tế của hệ thống |
| Hỗ trợ | Số ticket, thời gian phản hồi, thời gian xử lý, nhóm lỗi lặp lại | Cải thiện vận hành và kế hoạch bảo trì |

## 15. Điều kiện sẵn sàng đưa dịch vụ tới khách hàng

Trước khi đưa dịch vụ vào vận hành chính thức, cần có checklist sẵn sàng sau:

| Nhóm điều kiện | Bắt buộc đạt |
|---|---|
| Yêu cầu và nghiệm thu | SRS, use case, business flow, acceptance criteria và UAT record đã được duyệt |
| Kỹ thuật | Production environment sẵn sàng; domain/TLS/API gateway hoạt động; backup/restore đã thử; rollback plan có thể thực hiện |
| ANSVIS/AI | License/version xác nhận; pipeline/rule/model version rõ; shadow mode đạt; model rollback sẵn sàng |
| Dữ liệu | Consent/enrollment hợp lệ; retention policy chạy được; dữ liệu nhạy cảm được mã hóa; quyền xem dữ liệu đúng vai trò |
| Bảo mật | Không còn Critical/High; MFA Admin/BGH; secret không nằm trong source/log; audit log hoạt động |
| Web/Mobile | Luồng chính ổn định; push notification test đạt; mobile production build không chứa debug secret/log |
| Vận hành | Monitoring/alert hoạt động; runbook đầy đủ; người vận hành được đào tạo; kênh hỗ trợ và SLA rõ |
| Khách hàng | Đầu mối phê duyệt, đầu mối vận hành, đầu mối xử lý dữ liệu và quy trình phản hồi sự cố đã thống nhất |

Nếu bất kỳ điều kiện bắt buộc nào chưa đạt, hệ thống chỉ nên chạy ở trạng thái demo, staging, pilot hoặc shadow mode; không nên chuyển sang production chính thức.


## Phụ lục — Tài liệu tham chiếu ANSCENTER

- ANSVIS: <https://doc.anscenter.com.au/docs/ANSVIS/Introduction/>
- ANSTS: <https://doc.anscenter.com.au/docs/ANSTS/Introduction/>
- ANSTS Model Training: <https://doc.anscenter.com.au/docs/ANSTS/Model_Training/>
- ANSTS Evaluate & Export: <https://doc.anscenter.com.au/docs/ANSTS/Evaluate-Export/>
