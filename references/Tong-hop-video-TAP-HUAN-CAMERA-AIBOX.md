# TỔNG HỢP VIDEO TẬP HUẤN CAMERA AIBOX / ANSVIS

File video tham chiếu: `../assets/videos/TAP HUAN CAMERA AIBOX.mp4`

Tài liệu này tổng hợp nội dung chính của video cấp trên gửi, nhằm làm rõ video đang hướng dẫn phần nào, có thể dùng vào việc gì trong dự án AI Camera trường học, và phần nào vẫn cần bổ sung thêm tài liệu/quy trình riêng.

Lưu ý: nội dung dưới đây được tổng hợp dựa trên quan sát giao diện, frame trích từ video và luồng thao tác trong video. Đây không phải bản transcript lời nói đầy đủ.

---

## 1. Kết luận ngắn gọn

Video đang hướng dẫn cách vận hành nền tảng **AIBOX / ANSVIS Intelligent Vision System**, tập trung vào:

- Quản lý camera đầu vào.
- Cấu hình AI Task.
- Chọn model AI.
- Cấu hình rule phát hiện.
- Cấu hình vùng quan sát ROI.
- Theo dõi event/cảnh báo.
- Quản lý dữ liệu nhận diện khuôn mặt.
- Xuất/nhập event hoặc dataset.
- Cấu hình HTTP trigger/API để gửi kết quả AI sang hệ thống khác.
- Cấu hình server, GPU, license, storage và một số thông số vận hành.

Video phù hợp để dùng làm **tài liệu tham chiếu thao tác ANSVIS/AIBOX** trong dự án. Tuy nhiên, video không chứng minh rằng toàn bộ 6 nghiệp vụ của trường đã có model hoàn chỉnh sẵn. Video chủ yếu chứng minh ANSVIS có đủ cơ chế nền tảng: nhận camera, tạo AI Task, chọn model, cấu hình ROI/rule/threshold, xem Event Log và gửi event sang Backend qua HTTP Trigger.

Kết luận triển khai đúng:

- **Web/App/Backend** phải build riêng bằng mock/sanitized event, không chờ train AI.
- **ANSVIS Integration** là phần kết nối event từ ANSVIS sang Backend.
- **AI/model/pipeline** là phần riêng: dùng model có sẵn nếu đạt; custom pipeline/train/fine-tune nếu model hiện có không đủ.

---

## 2. Video này đang làm gì?

Video là một buổi tập huấn/demo thao tác trên phần mềm **ANSVIS Intelligent Vision System**. Đây là phần mềm dùng để nhận luồng camera, chạy các model AI, cấu hình rule phát hiện và sinh ra event/cảnh báo.

Trong dự án AI Camera trường học, ANSVIS/AIBOX có thể đóng vai trò là lớp xử lý video AI tại chỗ:

```text
Camera/IP Stream
    ↓
AIBOX / ANSVIS
    ↓
AI Task / Model / Rule / Event
    ↓
HTTP Trigger hoặc API
    ↓
Backend dự án
    ↓
Database / Notification / Web Portal / Mobile App
```

Nói cách khác, video không hướng dẫn xây toàn bộ hệ thống Web/Mobile/Backend, mà chủ yếu hướng dẫn cách dùng ANSVIS/AIBOX để tạo event AI từ camera.

---

## 3. Các nhóm chức năng chính xuất hiện trong video

| Nhóm chức năng | Nội dung video thể hiện | Ý nghĩa với dự án |
|---|---|---|
| Quản lý camera | Thêm/chọn camera IP, USB, edge, simulated camera; xem multi-view | Là đầu vào cho 34 camera của trường sau khi bên phần cứng bàn giao RTSP/API |
| AI Task | Tạo và quản lý task AI; start/stop task; chọn camera/model/class | Cấu hình từng nghiệp vụ như điểm danh, hút thuốc, xả rác, đồng phục, bảo hộ bếp |
| Model AI | Chọn model có sẵn hoặc custom model | Dùng model phù hợp cho từng loại phát hiện |
| Rule/ROI | Cấu hình vùng quan sát, confidence, presence, count, direction, duration | Giảm cảnh báo sai bằng cách giới hạn vùng/kịch bản phát hiện |
| Face Recognition | Quản lý nhận diện khuôn mặt, ghi nhận mặt, nhóm người | Dùng cho điểm danh học sinh và chấm công cán bộ |
| Event Log | Xem danh sách event, ảnh/snapshot, bounding box, confidence, export/import | Là nguồn dữ liệu để backend ghi nhận attendance/violation |
| HTTP Trigger/API | Cấu hình URL, token, JSON payload, gửi ảnh/video kèm event | Cách ANSVIS đẩy dữ liệu sang backend của dự án |
| Server/Storage | Cấu hình license, GPU engine, external storage, backup/restore | Liên quan đến vận hành production |
| Dataset/Export | Export dữ liệu/event/dataset phục vụ huấn luyện hoặc kiểm tra | Có thể dùng làm feedback loop để cải thiện model |

---

## 4. Timeline nội dung trong video

| Khoảng thời gian | Nội dung chính | Diễn giải |
|---|---|---|
| 00:00:00 – 00:06:00 | AI Task Configuration và multi-view | Danh sách task AI, trạng thái start/stop, xem nhiều camera |
| 00:06:00 – 00:16:00 | Camera Configuration | Quản lý nguồn camera/video, camera IP/simulated camera, thông tin stream |
| 00:16:00 – 00:32:00 | Face Recognition Service | Quản lý người/nhóm, face recording, known/unknown, thiết lập nhận diện khuôn mặt |
| 00:32:00 – 00:43:00 | ROI/rule và ví dụ detection | Vẽ vùng quan sát, xem bounding box, class, confidence, rule phát hiện |
| 00:43:00 – 00:48:00 | Event Log Management | Danh sách event, lọc event, xem kết quả model/rule, đối soát output AI |
| 00:48:00 – 01:02:00 | HTTP Trigger / API | Cấu hình trigger, URL backend, payload JSON, token/header, test gửi event |
| 01:02:00 – 01:16:00 | Lưu trữ / server / cloud / file | Cấu hình lưu trữ, upload, thư mục dữ liệu, kiểm soát nơi lưu media/event |
| 01:16:00 – 01:30:00 | Trigger configuration nâng cao | Cấu hình điều kiện trigger, schedule, event group, action, tham số gửi đi |
| 01:30:00 – 01:40:00 | ROI/rule/task thực tế | Cấu hình vùng ROI, test rule trên video thật, kiểm soát event theo vùng |
| 01:40:00 – 01:46:30 | Model Management và Camera Configuration | Danh sách model server, upload model zip, quay lại danh sách camera/task |

---

## 5. Video hướng dẫn những thao tác gì?

### 5.1 Quản lý camera đầu vào

Video thể hiện cách phần mềm nhận và quản lý nhiều loại nguồn video:

- Camera IP.
- Camera USB.
- Camera edge/onboard.
- Camera giả lập/simulated camera.
- Chế độ xem nhiều camera cùng lúc.
- Kiểm tra trạng thái nguồn hình ảnh.

Áp dụng vào dự án:

- Sau khi khách hàng/đơn vị thi công bàn giao RTSP/ONVIF/API, đội phần mềm dùng thông tin đó để cấu hình camera trong ANSVIS.
- Mỗi camera cần được ánh xạ với khu vực, nghiệp vụ và model tương ứng.

Ví dụ:

| Camera | Khu vực | Nghiệp vụ AI |
|---|---|---|
| Camera cổng trường | Cổng vào | Điểm danh, đi trễ |
| Camera sân trường | Sân trường | Xả rác, hút thuốc |
| Camera hành lang | Hành lang | Đồng phục, hành vi vi phạm |
| Camera bếp ăn | Bếp ăn | Bảo hộ bếp |

---

### 5.2 Tạo và cấu hình AI Task

Video có phần quản lý **AI Task**. Đây là nơi cấu hình một tác vụ AI cụ thể.

Một AI Task thường gồm:

- Camera đầu vào.
- Model AI cần chạy.
- Class/nhãn cần phát hiện.
- Vùng quan sát ROI.
- Ngưỡng confidence.
- Rule phát hiện.
- Hành động khi có event.
- Lịch chạy/schedule.
- Cách gửi event ra ngoài.

Áp dụng vào dự án:

- Mỗi nghiệp vụ AI nên được tách thành task rõ ràng.
- Không nên cấu hình chung tất cả nghiệp vụ vào một task nếu gây khó kiểm soát.

Ví dụ task:

| Task | Camera | Model | Event sinh ra |
|---|---|---|---|
| Attendance Gate | Camera cổng | Face recognition | Học sinh/cán bộ xuất hiện |
| Smoking Detection | Camera sân/hành lang | Smoking pipeline/model nếu có | Nghi vấn hút thuốc, cần người xác nhận |
| Littering Detection | Camera sân | Littering pipeline/model nếu có | Nghi vấn xả rác theo hành vi |
| Uniform Detection | Camera cổng/hành lang | Uniform pipeline/model nếu có | Phát hiện sai đồng phục |
| Kitchen PPE Detection | Camera bếp | PPE pipeline/model nếu có | Thiếu mũ/tạp dề/khẩu trang theo quy định |

---

### 5.3 Chọn model và class cần phát hiện

Trong video có phần Model Management và chọn model/class. Đối chiếu với ảnh chụp `Model Management - Server List` hiện tại, máy ANSVIS đang có các nhóm model chính:

- Face Detection.
- Facial Recognition.
- Generic Object Detection.
- Objects, trong đó có một số class vật thể như `garbage`, `basket`, `bucket`.
- Helmet/no helmet.
- Fire/Smoke.
- Vehicle Detection.
- OCR / License Plate Recognition.
- Pet.

Không nên suy luận rằng đã có sẵn model hoàn chỉnh cho hút thuốc, đồng phục học sinh, xả rác theo hành vi hoặc PPE bếp chỉ vì ANSVIS hỗ trợ chọn model/class.

Áp dụng vào dự án:

- Dùng model có sẵn nếu model đủ phù hợp.
- Dùng custom model nếu nghiệp vụ cần nhận diện đặc thù của trường, ví dụ đồng phục riêng hoặc bảo hộ bếp theo quy định riêng.
- Mỗi model phải có version, ngưỡng confidence, kết quả đánh giá và khả năng rollback.
- Riêng xả rác, hút thuốc, đồng phục học sinh và PPE bếp phải có bước baseline/shadow mode trước khi kết luận có cần train/fine-tune hay không.

---

### 5.4 Cấu hình ROI và rule phát hiện

Video thể hiện việc cấu hình rule như:

- Vùng quan sát ROI.
- Confidence threshold.
- Presence/duration.
- Count.
- Direction.
- Size.
- Tracker.
- Chống trùng/giảm event lặp.

Ý nghĩa:

- AI model chỉ là một phần. Muốn cảnh báo ít sai, cần cấu hình đúng rule và vùng quan sát.
- Cùng một model nhưng ROI/threshold khác nhau sẽ cho chất lượng event khác nhau.

Áp dụng vào dự án:

| Nghiệp vụ | Rule cần chú ý |
|---|---|
| Điểm danh | Chỉ xét vùng cổng vào; chống ghi nhận trùng; xử lý unknown face |
| Đi trễ | So sánh thời điểm event với giờ học/ca làm |
| Xả rác | Cần rule theo hành vi và vùng sân; tránh nhầm vật thể rơi sẵn |
| Hút thuốc | Cần threshold cao và human review do dễ sai |
| Đồng phục | Phụ thuộc mẫu đồng phục, ánh sáng, góc camera |
| Bảo hộ bếp | Chỉ áp dụng trong ROI khu bếp, tránh cảnh báo ngoài vùng |

---

### 5.5 Nhận diện khuôn mặt

Video có phần liên quan tới:

- Face recording.
- User/person group.
- Known/unknown face.
- Nhóm người.
- Blacklist/VIP/custom group.
- Min face score.
- Min face size.
- Số ảnh tối đa trên mỗi ID.

Áp dụng vào dự án:

- Dùng cho điểm danh học sinh và chấm công cán bộ.
- Cần có quy trình enrollment rõ ràng.
- Chỉ enrollment khi đã có consent hợp lệ.
- Face embedding/ảnh khuôn mặt phải được mã hóa và quản lý retention.
- Kết quả nhận diện confidence thấp phải chuyển sang unknown/human review.

Không nên dùng nhận diện khuôn mặt như kết luận tuyệt đối. Cần có cơ chế chỉnh sửa thủ công và audit.

---

### 5.6 Event Log và xuất/nhập dữ liệu

Video thể hiện màn hình Event Log, bao gồm:

- Danh sách event.
- Ảnh/snapshot.
- Bounding box.
- Confidence.
- Thông tin model/rule.
- Export event JSON.
- Import event JSON.
- Export dataset/XML/classification.
- Export face image hoặc face record CSV.

Áp dụng vào dự án:

- Event Log là nguồn để đối chiếu khi backend nhận event.
- Có thể dùng event sai/đúng làm feedback để cải thiện model.
- Export event giúp debug khi có tranh chấp hoặc lỗi nghiệp vụ.
- Cần kiểm soát quyền truy cập vì event có thể chứa ảnh học sinh/cán bộ.

---

### 5.7 HTTP Trigger/API gửi event sang backend

Đây là phần rất quan trọng với dự án.

Video thể hiện khả năng cấu hình:

- HTTP trigger.
- URL backend nhận event.
- Bearer token/login token.
- Custom JSON payload.
- Gửi kèm ảnh/video.
- Test trigger.
- Schedule/periodic trigger.

Áp dụng vào kiến trúc dự án:

```text
ANSVIS Event
    ↓ HTTP Trigger / API
Backend Event Ingestion
    ↓
Validate schema
    ↓
Check duplicate/replay
    ↓
Save database/object storage
    ↓
Apply business rule
    ↓
Notification / Dashboard / Report
```

Các yêu cầu bắt buộc khi tích hợp:

- Backend phải có endpoint riêng để nhận event từ ANSVIS.
- Có token/signature để xác thực event.
- Có schema validation để tránh dữ liệu sai format.
- Có cơ chế chống event trùng.
- Có retry/idempotency.
- Không log token, ảnh nhạy cảm hoặc dữ liệu sinh trắc học không cần thiết.

Thiết kế backend không được phụ thuộc trực tiếp vào raw payload của ANSVIS. Cần có lớp **ANSVIS Adapter** để validate, normalize và chuyển event thành schema nội bộ. Cách này giúp Web/App/Backend ít bị ảnh hưởng nếu ANSVIS đổi payload, đổi model hoặc đổi cách đặt tên task.

---

## 6. Video có thể dùng cho phần AI training không?

Có thể dùng, nhưng chỉ dùng được một phần.

### 6.1 Phần có thể dựa vào video

| Nội dung | Có thể dùng video làm cơ sở không? | Ghi chú |
|---|---:|---|
| Cấu hình camera vào ANSVIS | Có | Video thể hiện cách quản lý nguồn video |
| Cấu hình AI Task | Có | Đây là phần trọng tâm của video |
| Chọn model/class | Có | Có thể chuẩn hóa thao tác chọn model |
| Cấu hình ROI/rule/threshold | Có | Rất hữu ích cho triển khai thực tế |
| Xem event và debug kết quả AI | Có | Dùng để kiểm tra event đúng/sai |
| Cấu hình HTTP trigger/API | Có | Phục vụ tích hợp backend |
| Import/custom model | Một phần | Cần xác minh thêm format model và version |
| Export dataset/event | Một phần | Có thể dùng cho feedback loop |

### 6.2 Phần video chưa đủ

Video chưa đủ để thay thế các tài liệu/quy trình sau:

- Quy chuẩn dataset.
- Quy trình xin consent dữ liệu khuôn mặt học sinh.
- Quy trình gán nhãn dữ liệu.
- Cách chia train/validation/test.
- Cách train model chi tiết trên ANSTS hoặc công cụ khác.
- Cách đánh giá model bằng precision, recall, F1, mAP, FAR/FRR.
- Model card.
- Threshold report.
- Shadow mode report.
- Quy trình rollback model.
- Tiêu chí nghiệm thu AI với khách hàng.

Vì vậy, không nên nói “AI train chỉ dựa theo video này”. Cách nói đúng là:

> Quy trình vận hành và cấu hình AI trên AIBOX/ANSVIS sẽ tham chiếu theo video tập huấn. Riêng phần huấn luyện, đánh giá và nghiệm thu model AI sẽ có quy trình bổ sung để đảm bảo chất lượng production.

---

## 7. Quy trình đề xuất dựa trên video cho dự án

### Bước 1 — Xác minh nền tảng AIBOX/ANSVIS

- Xác nhận version phần mềm.
- Xác nhận license.
- Xác nhận số lượng camera/channel được hỗ trợ.
- Xác nhận GPU/CPU/RAM.
- Xác nhận model có sẵn.
- Xác nhận custom model có thể import không.
- Xác nhận API/HTTP trigger.

Đầu ra:

- Capability/gap matrix.
- Danh sách phần dùng được ngay.
- Danh sách phần cần bổ sung hoặc workaround.

---

### Bước 2 — Cấu hình camera mẫu

- Nhận RTSP/ONVIF/API từ đơn vị phần cứng.
- Cấu hình 1–3 camera mẫu vào ANSVIS.
- Kiểm tra chất lượng hình ảnh.
- Kiểm tra reconnect.
- Kiểm tra time sync.
- Kiểm tra độ trễ.

Đầu ra:

- Camera connection matrix.
- Stream health report.

---

### Bước 3 — Tạo AI Task mẫu / pipeline mẫu

- Tạo task điểm danh.
- Tạo task/pipeline phát hiện hút thuốc.
- Tạo task/pipeline phát hiện xả rác.
- Tạo task/pipeline phát hiện đồng phục.
- Tạo task/pipeline phát hiện bảo hộ bếp.

Mỗi task cần ghi rõ:

- Camera.
- Model.
- Class.
- ROI.
- Confidence.
- Rule.
- Schedule.
- Event action.
- HTTP trigger.

Đầu ra:

- AI Task configuration sheet.
- Pipeline spec cho 4 nghiệp vụ custom nếu model hiện có chưa đủ.

---

### Bước 4 — Kết nối HTTP Trigger về backend

- Tạo endpoint backend nhận event.
- Cấu hình URL trong ANSVIS.
- Cấu hình token.
- Cấu hình JSON payload.
- Test gửi event.
- Kiểm tra ảnh/video đính kèm nếu có.
- Kiểm tra retry khi backend lỗi.

Đầu ra:

- Event API contract.
- Event ingestion test report.

---

### Bước 5 — Đánh giá event AI

- Chạy thử trên camera mẫu.
- Ghi nhận event đúng.
- Ghi nhận event sai.
- Ghi nhận event bỏ sót.
- Điều chỉnh ROI/rule/threshold.
- So sánh trước/sau khi chỉnh.

Đầu ra:

- Calibration report.
- False alert report.
- Threshold report.

---

### Bước 6 — Training/fine-tune nếu model/pipeline chưa đạt

Nếu model có sẵn chưa đạt yêu cầu, cần chuyển sang quy trình training/fine-tune:

- Thu thập dữ liệu hợp lệ.
- Gán nhãn.
- Tách train/validation/test.
- Train/fine-tune model.
- Evaluate.
- Export model.
- Import vào ANSVIS.
- Test lại trên camera mẫu.

Đầu ra:

- Dataset report.
- Model card.
- Evaluation report.
- Model release package.

Điểm quan trọng: training/fine-tune không phải điều kiện để bắt đầu xây Web/App/Backend. Web/App/Backend phải chạy được trước bằng mock/sanitized event cho đủ 6 chức năng. Training/fine-tune chỉ là nhánh nâng chất lượng cho 4 pipeline custom nếu baseline/shadow mode không đạt.

---

### Bước 7 — Shadow mode

- Chạy AI với dữ liệu thật nhưng chưa dùng để cảnh báo chính thức.
- So sánh kết quả AI với người kiểm tra.
- Đo false positive/false negative.
- Hiệu chỉnh lại threshold/rule.
- Chỉ bật cảnh báo chính thức khi đạt ngưỡng nghiệm thu.

Đầu ra:

- Shadow mode report.
- AI sign-off.

---

### Bước 8 — Mở rộng dần tới 34 camera

Không nên cấu hình toàn bộ 34 camera cùng lúc ngay từ đầu.

Thứ tự đề xuất:

1. Cấu hình camera mẫu theo từng nghiệp vụ.
2. Kiểm tra event và hiệu năng.
3. Mở rộng theo từng nhóm camera.
4. Benchmark CPU/GPU/RAM/network/storage.
5. Theo dõi queue backlog và độ trễ event.
6. Chốt cấu hình production.

Đầu ra:

- 34-camera rollout checklist.
- Capacity report.
- Production readiness report.

---

## 8. Những việc cần đưa vào kế hoạch phát triển

Từ video, nên bổ sung hoặc nhấn mạnh các task sau trong kế hoạch:

| Nhóm | Task cần có |
|---|---|
| ANSVIS setup | Cài đặt, active license, khóa version, cấu hình user/admin |
| Camera input | Cấu hình camera IP/RTSP/API, kiểm tra stream health |
| AI Task | Tạo task theo từng nghiệp vụ, cấu hình model/class/ROI/rule |
| AI Task Group | Cấu hình nhóm task và model sharing nếu cần |
| Face recognition | Thiết lập enrollment, known/unknown, nhóm người, min face score |
| Model capability | Kiểm rõ model nào có sẵn, model nào chỉ làm baseline, model nào cần custom |
| Event Log | Kiểm tra event, export/import JSON, lưu snapshot có kiểm soát |
| HTTP Trigger | Cấu hình URL, token, custom JSON, ảnh/video đính kèm |
| Backend adapter | Nhận event, validate schema, chống trùng, retry, audit |
| Storage | Cấu hình external storage, retention, backup/restore |
| Security | Bảo vệ credential, token, event payload, quyền truy cập ảnh/event |
| Monitoring | Theo dõi task stopped, camera offline, event fail, GPU/CPU |
| Benchmark | Test hiệu năng khi mở rộng lên 34 camera |

---

## 9. Rủi ro nếu chỉ dựa vào video

| Rủi ro | Tác động | Cách xử lý |
|---|---|---|
| Video chỉ là hướng dẫn thao tác, không phải spec kỹ thuật | Dễ thiếu API contract, data schema, security rule | Viết thêm SRS/API spec/event flow |
| Không có transcript chi tiết | Có thể bỏ sót chi tiết thao tác | Dùng video để thao tác lại trên phần mềm thật và ghi checklist |
| Không rõ version/license thực tế | Tính năng trong video có thể khác bản được cấp | Xác minh version/license trước khi cam kết |
| Model có sẵn chưa phù hợp môi trường trường học | AI báo sai hoặc bỏ sót | Chạy shadow mode và fine-tune nếu cần |
| Chưa có benchmark 34 camera | Có thể thiếu GPU/CPU/storage | Test tải theo nhóm camera |
| HTTP trigger/API chưa được kiểm tra bảo mật | Có thể bị event giả hoặc lộ dữ liệu | Dùng token/signature, TLS, validation, audit |

---

## 10. Cách trình bày với cấp trên/khách hàng

Cách nói nên dùng:

> Video tập huấn AIBOX/ANSVIS là tài liệu tham chiếu chính để đội phát triển nắm quy trình cấu hình camera, AI Task, model, rule, event log và HTTP trigger. Đội phát triển sẽ dựa trên video này để thiết kế quy trình tích hợp ANSVIS với backend dự án. Tuy nhiên, để đưa vào production cho trường học, cần bổ sung quy trình riêng cho training/evaluation model, bảo mật dữ liệu sinh trắc học, kiểm thử E2E, shadow mode, benchmark 34 camera và nghiệm thu AI.

Không nên nói:

> Chỉ cần xem video này là đủ để train và triển khai AI.

Lý do: video chủ yếu hướng dẫn vận hành/cấu hình nền tảng, không bao phủ đầy đủ tiêu chuẩn chất lượng production.

---

## 11. Kết luận

Video này rất hữu ích cho dự án, đặc biệt ở phần:

- Hiểu cách AIBOX/ANSVIS nhận camera.
- Tạo AI Task.
- Chọn model.
- Cấu hình ROI/rule/threshold.
- Theo dõi event.
- Gửi event sang backend qua HTTP trigger/API.
- Quản lý một số phần vận hành như GPU, license, storage.

Tuy nhiên, để triển khai dịch vụ ổn định cho khách hàng, video chỉ nên được xem là **tài liệu thao tác nền tảng ANSVIS**, không phải toàn bộ quy trình AI training/production và cũng không thay thế được plan Web/App/Backend.

Phần cần làm thêm:

- SRS.
- Event flow.
- API contract.
- Dataset/labelling guideline.
- Model evaluation.
- Shadow mode.
- Security/privacy checklist.
- Performance benchmark.
- UAT và acceptance criteria.

Kết luận thực tế:

> Có thể dùng video làm cơ sở triển khai ANSVIS/AIBOX và tích hợp event sang Backend. Web/App/Backend phải được build độc lập bằng mock/sanitized event. 4 pipeline xả rác, hút thuốc, đồng phục học sinh và PPE bếp cần baseline/shadow mode; chỉ training/fine-tune khi model hiện có không đạt yêu cầu.
