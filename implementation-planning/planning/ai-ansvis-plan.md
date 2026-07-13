# AI, ANSVIS and data safety plan

## Cách đọc file này

File này chỉ tập trung vào ANSVIS, AI Task, model/pipeline, shadow mode và custom training khi cần.

Kế hoạch điều phối tổng thể đã tách riêng Web/App/Backend, ANSVIS Integration và AI Training nằm ở [workstream-implementation-plan.md](workstream-implementation-plan.md). Khi build Web/Mobile/Backend, không được coi việc train AI là phụ thuộc mặc định; Web/App/Backend phải chạy được bằng mock/sanitized ANSVIS event.

Danh sách model ANSVIS đã có/chưa có và hướng xử lý từng chức năng nằm ở [ansvis-model-capability-matrix.md](ansvis-model-capability-matrix.md). File này là nguồn chuẩn để quyết định model nào dùng ngay, pipeline nào cần custom.

## Vai trò của ANSVIS/ANSTS

Theo tài liệu ANSCENTER, ANSVIS là nền tảng video analytics dùng để nhận camera, chạy AI Task, tạo Event Log và gửi event sang hệ thống ngoài qua trigger. ANSTS là công cụ tạo/labelling/train/evaluate/export model computer vision để deploy sang ANSVIS/ANSDL.

## Hướng triển khai AI đã chốt

Theo xác nhận từ cấp trên, nội dung video tập huấn AIBOX/ANSVIS và tài liệu ANSCENTER, hướng triển khai đúng là: **ưu tiên dùng khả năng có sẵn của ANSVIS/AIBOX để nhận camera, chạy AI Task/model, sinh Event Log và gửi event sang Backend qua HTTP Trigger**. Team phần mềm không mặc định phải train AI từ đầu.

Với phạm vi hiện tại, ANSVIS có thể dùng trực tiếp cho nhóm nhận diện khuôn mặt/chấm công vì đã có `Face Detection` và `Facial Recognition`. Tuy nhiên các nhóm xả rác, hút thuốc, đồng phục học sinh và PPE/bảo hộ bếp là bài toán đặc thù hơn; các nhóm này cần được thiết kế như **custom pipeline/model/rule** trên nền ANSVIS, không coi là model có sẵn chắc chắn đáp ứng ngay.

Sau khi trích frame và xem lại video, cần hiểu video theo cách sau:

- Video chứng minh ANSVIS có workflow cấu hình camera, AI Task, model, ROI/rule, Event Log, HTTP Trigger, storage và Model Management.
- Video không thay thế SRS, API contract, database design, security/privacy plan hoặc UAT.
- Video không đủ để kết luận đã có sẵn model production cho xả rác, hút thuốc, đồng phục học sinh và PPE bếp.
- Vì vậy, phần AI phải đi theo pipeline kiểm chứng: **spec -> baseline -> shadow -> evaluate -> train/fine-tune nếu cần -> shadow lại -> nghiệm thu**.

Training/fine-tune bằng ANSTS là nhánh triển khai cho các pipeline đặc thù nếu model có sẵn trong ANSVIS không đủ chính xác hoặc thiếu class cần nhận diện.

Nếu có training/fine-tune/kiểm định AI, dữ liệu của dự án **chỉ lấy từ camera đang sử dụng qua ANSVIS/AIBOX**. Không mặc định dùng dataset bên ngoài, dữ liệu tải từ Internet, dữ liệu trường khác hoặc dữ liệu cá nhân tự thu thập.

Ý nghĩa triển khai:

- ANSVIS/AIBOX là nguồn thu thập dữ liệu camera chính cho AI.
- ANSTS không phải hạng mục bắt buộc ban đầu; chỉ dùng để label/train/evaluate/export model khi cần custom/fine-tune.
- Mọi dữ liệu đưa vào training phải có manifest ghi rõ camera/source, thời gian, mục đích, consent status, label list, checksum, người duyệt và retention.
- Nếu dữ liệu có khuôn mặt/học sinh, phải kiểm tra consent trước khi lưu, label, train, evaluate hoặc export.
- Không copy dữ liệu ANSVIS ra máy cá nhân/cloud ngoài nếu chưa có ticket, mã hóa, audit và phê duyệt.
- Dataset thật không nằm trong Git; repo chỉ chứa schema, script, manifest mẫu và fixture đã giả lập/sanitize.

Nguyên tắc quan trọng:

- Không chờ dataset thật mới bắt đầu xây dựng hệ thống. Backend, Web, Mobile, database, ANSVIS Adapter, event schema, consent, audit, dashboard và notification phải được chuẩn bị trước bằng mock/sanitized event.
- Không cam kết độ chính xác AI cuối cùng trước khi có dữ liệu thực tế từ camera trường học.
- Model ban đầu ưu tiên dùng built-in/prebuilt model và AI Task sẵn có trong ANSVIS.
- Facial Recognition dùng model có sẵn của ANSVIS, còn các pipeline đặc thù phải được đánh giá riêng bằng dữ liệu camera thật.
- Custom model/training bằng ANSTS hoặc model import sẽ trở thành việc chính cho các pipeline xả rác, hút thuốc, đồng phục học sinh, PPE bếp nếu model có sẵn không đủ class/logic.
- Mỗi nhóm AI task vẫn phải có cấu hình camera/ROI/threshold, shadow mode và nghiệm thu riêng trước production.

## Kiểm kê model hiện có trên máy ANSVIS

Theo ảnh chụp màn hình ANSVIS `Model Management - Server List`, máy hiện có các model built-in/prebuilt sau:

| Model hiện có | Loại | Có thể dùng cho |
|---|---|---|
| `Face Detection` | Face detector | Phát hiện khuôn mặt trước khi nhận diện |
| `Facial Recognition` | Face recognizer | Điểm danh học sinh, chấm công giáo viên/cán bộ |
| `ANS_GenericOD(GPU)` | Object detection đa lớp | Person/object baseline, hỗ trợ pipeline tùy chỉnh |
| `ANS_Objects` | Object detection | Một số vật thể phổ biến, hỗ trợ thử nghiệm baseline |
| `ANS_Helmet` | Detection | Có thể tham khảo cho PPE/bảo hộ nếu class phù hợp |
| `ANS_FireSmoke` | Detection | Không phải trọng tâm, có thể hỗ trợ cảnh báo khói nếu điều kiện camera phù hợp |
| `ANS_VehicleDetection` | Detection | Không thuộc 6 chức năng chính hiện tại |
| `OCR`, `License Plate Recognition(VN)`, `ANS_Pet` | OCR/LPR/Detection | Không thuộc 6 chức năng chính hiện tại |

Kết luận kỹ thuật:

- Nhận diện khuôn mặt/chấm công có thể bắt đầu bằng model có sẵn.
- Xả rác, hút thuốc, đồng phục học sinh và PPE bếp chưa thể khẳng định dùng model có sẵn là đủ.
- Các model object detection hiện có có thể dùng làm baseline hoặc thành phần pipeline, nhưng cần shadow mode và nghiệm thu thực tế.

## Phân nhóm chức năng và model/pipeline

| Nhóm | Chức năng | Model/pipeline | Trạng thái model | Ghi chú |
|---|---|---|---|---|
| Nhóm 1 - Face attendance/timekeeping | Điểm danh học sinh | Facial Recognition dùng chung | Có sẵn trong ANSVIS | Backend quyết định có mặt/vắng/đi muộn/check-in/check-out theo lịch học |
| Nhóm 1 - Face attendance/timekeeping | Chấm công giáo viên/cán bộ | Facial Recognition dùng chung | Có sẵn trong ANSVIS | Backend xử lý ca làm, giờ vào/ra, đi muộn, về sớm, ngày công |
| Nhóm 2 - Behavior violation | Xả rác | Littering Detection pipeline | Custom pipeline/model/rule | Cần person/object tracking, vùng bỏ rác hợp lệ, logic vật bị bỏ lại sau khi người rời đi |
| Nhóm 2 - Behavior violation | Hút thuốc | Smoking Detection pipeline | Custom pipeline/model/rule | Trả kết quả `nghi vấn hút thuốc`, cần human review vì dễ nhầm với bút/điện thoại/ăn uống |
| Nhóm 3 - Uniform/PPE | Đồng phục học sinh | Student Uniform Detection | Custom model/pipeline | Cần chốt quy định đồng phục, class như `uniform_correct`, `uniform_incorrect`, `student_card` |
| Nhóm 3 - Uniform/PPE | Bảo hộ bếp | Kitchen PPE Detection | Custom model/pipeline | Cần nhận diện mũ, khẩu trang, tạp dề, găng tay, đồng phục bếp, giày bảo hộ |

## Thứ tự triển khai AI khuyến nghị

| Thứ tự | Hạng mục | Lý do |
|---|---|---|
| 1 | Điểm danh học sinh và chấm công giáo viên | Dùng chung Facial Recognition có sẵn, backend/rule nghiệp vụ là phần chính |
| 2 | Kitchen PPE Detection | Phạm vi khu vực rõ, rule rõ, có thể tận dụng object/person/helmet baseline |
| 3 | Student Uniform Detection | Cần chốt quy định đồng phục và dữ liệu mẫu theo trường |
| 4 | Littering Detection | Là pipeline hành vi, cần dữ liệu video thực tế và tracking |
| 5 | Smoking Detection | Khó nhất trong nhóm vi phạm vì vật thể nhỏ, camera xa, dễ false positive |

Nguồn tham chiếu chính:

- https://doc.anscenter.com.au/
- https://doc.anscenter.com.au/docs/ANSVIS/Introduction/
- https://doc.anscenter.com.au/docs/ANSVIS/Getting-Started/System-Requirement/
- https://doc.anscenter.com.au/docs/ANSVIS/Guides/Camera/
- https://doc.anscenter.com.au/docs/ANSVIS/Guides/Prebuilt-AI-Tasks/
- https://doc.anscenter.com.au/docs/ANSVIS/Guides/Custom-AI-Tasks/First-Step/
- https://doc.anscenter.com.au/docs/ANSVIS/Advanced-Guides/Event-Trigger/HTTP/
- https://doc.anscenter.com.au/docs/ANSVIS/Advanced-Guides/Facial-Recognition-Service/
- https://doc.anscenter.com.au/docs/ANSVIS/System-Setting/Event-Storage/
- https://doc.anscenter.com.au/docs/ANSVIS/System-Setting/Cloud-Image-Upload/
- https://doc.anscenter.com.au/docs/ANSVIS/System-Setting/Restore-Settings/
- https://doc.anscenter.com.au/docs/ANSTS/Introduction/
- https://doc.anscenter.com.au/docs/ANSTS/Model_Training/
- https://doc.anscenter.com.au/docs/ANSTS/Evaluate-Export/

## Luồng AI event

```text
Camera RTSP/ONVIF
  -> ANSVIS/AIBOX AI Task
  -> ANSVIS Event Log
  -> HTTP Trigger
  -> API Gateway
  -> ANSVIS Adapter
  -> Event Ingestion
  -> Queue/Outbox
  -> Attendance / Violation / Notification / Report
```

## Điểm cần bám theo ANSCENTER docs

| Chủ đề | Nội dung quan trọng | Ảnh hưởng thiết kế |
|---|---|---|
| ANSVIS system | Chạy trên máy vật lý, Windows khuyến nghị, cần GPU/license phù hợp | Không thiết kế như container service bình thường |
| Camera | Hỗ trợ RTSP/ONVIF, capture rate ảnh hưởng tải | Cần pilot tải thật với 34 camera |
| AI Task | Có schedule, ROI, threshold, model score, event trigger | Cấu hình phải version và có runbook |
| Custom Task Group | Gom camera/model/task, start/stop theo nhóm | Hữu ích cho quản lý task trường học |
| HTTP Trigger | POST event, append image/video, custom payload, login/token, debug mode | Backend cần validate, auth, idempotency; debug off production |
| Event Storage | Max Events overwrite, storage thấp tự xóa event cũ | Backend không được phụ thuộc ANSVIS Event Storage là kho duy nhất |
| Cloud Storage | Upload image/video lên S3/GCS/custom endpoint | Bucket phải private, signed URL |
| Backup Settings | Restore point có thể không backup face DB/model/license | Cần backup riêng model/dataset/face DB nếu được phép |
| Face Recognition | User/group, face image, recording, threshold, import/export face DB | Đây là vùng dữ liệu sinh trắc học rủi ro cao |
| ANSTS | Label/train/evaluate/export model khi cần custom/fine-tune | Không phải scope mặc định; nếu dùng thì mỗi model cần registry, metric, approval |

## AI data security

Không được:

- Commit dataset, ảnh mặt, video camera, event JSON thật.
- Dùng tên thật học sinh trong folder dataset.
- Dùng dataset ngoài/Internet/trường khác làm dữ liệu mặc định cho training, benchmark hoặc demo.
- Gửi dataset thật lên dịch vụ ngoài khi chưa được duyệt.
- Log raw event có ảnh/base64/face data.
- Bật ANSVIS Debug Mode trong production.
- Cho export face DB không có ticket/audit.

Phải làm:

- Dataset dùng mã định danh giả.
- Có dataset manifest: nguồn, thời gian, consent, số lượng, label, checksum, retention.
- Model artifact có version, checksum, metric, reviewer.
- Có shadow mode trước production.
- Có human review cho sự kiện nhạy cảm hoặc confidence thấp.

## Plan triển khai AI theo hướng ANSVIS-first

| Phase AI | Mục tiêu | Công việc chính | Output/Gate |
|---|---|---|---|
| AI-01 - Chốt phạm vi AI task | Xác định chính xác 6 chức năng, 3 nhóm lớn và camera nào phục vụ task nào | Lập ma trận 34 camera theo nhóm: face attendance/timekeeping, behavior violation, uniform/PPE; xác định ROI, giờ hoạt động, event type, mức nhạy cảm dữ liệu | Có 34-camera task mapping, scope từng task, data sensitivity |
| AI-02 - Cấu hình Facial Recognition | Dùng model có sẵn cho điểm danh/chấm công | Cấu hình Face Detection, Facial Recognition, danh sách người, camera, threshold, Event Log, HTTP Trigger | Nhận được event face recognition dùng cho học sinh/giáo viên |
| AI-03 - Thiết kế 4 custom pipeline vi phạm | Làm rõ pipeline/model/rule cho xả rác, hút thuốc, đồng phục, PPE bếp | Viết spec từng pipeline: class, ROI, rule, input/output event, human review, metric nghiệm thu | Có pipeline spec được duyệt trước khi build/test |
| AI-04 - Chuẩn bị backend/app/web trước khi có dataset thật | Sẵn sàng nhận event và hiển thị kết quả khi camera bắt đầu thu dữ liệu | Xây ANSVIS Adapter, event schema, database, audit, consent, Web dashboard, Mobile notification/detail screen bằng mock/sanitized event | App/Web/API chạy E2E bằng mock event, không cần dữ liệu thật |
| AI-05 - Tích hợp camera thật tại trường | Khi camera được đưa vào sử dụng, ANSVIS xử lý trực tiếp luồng camera | Cấu hình camera vào ANSVIS, task, ROI, threshold, Event Log, storage, quyền truy cập, tắt debug production | ANSVIS nhận camera và sinh event đúng nghiệp vụ |
| AI-06 - Shadow mode và hiệu chỉnh | Đánh giá kết quả từng model/pipeline trong môi trường thật | Chạy quan sát, đo false positive/false negative, chỉnh ROI/threshold/rule, không tự động kết luận sự kiện nhạy cảm | Shadow report, threshold/rule đề xuất |
| AI-07 - Custom training/fine-tune cho pipeline chưa đạt | Chỉ dùng cho xả rác/hút thuốc/đồng phục/PPE nếu baseline không đạt | Thu dataset hợp lệ từ ANSVIS/camera, manifest, label, train/evaluate bằng ANSTS hoặc model import, shadow mode lại | Model custom/fine-tune có version, metric, approval |
| AI-08 - Nghiệm thu AI task/pipeline | Duyệt từng nhóm task trước production | Demo kết quả, thống kê lỗi, thống nhất ngưỡng chấp nhận, quy định human review/appeal | Biên bản nghiệm thu AI task hoặc danh sách task cần cải thiện |
| AI-09 - Production rollout | Bật chính thức có kiểm soát | Bật từng nhóm camera/task, theo dõi alert, rollback config/model nếu lỗi, audit khi xem/export evidence | AI chạy production, có rollback, monitor và runbook |
| AI-10 - Continuous improvement | Duy trì chất lượng sau go-live | Theo dõi drift, false alert, missed detection, thu thêm sample hợp lệ nếu cần retrain | Config/model version mới chỉ lên production sau shadow mode |

## Tách rõ việc của AI, ANSVIS Integration và Product Platform

| Hạng mục | Thuộc luồng nào | Có phụ thuộc dataset/training không? | Ghi chú |
|---|---|---:|---|
| Mock/sanitized event cho 6 chức năng | Product Platform + ANSVIS Integration | Không | Bắt buộc làm sớm để Web/App/Backend phát triển độc lập |
| API nhận event từ ANSVIS | ANSVIS Integration | Không | Chỉ cần event contract và fixture sạch |
| Dashboard camera/task/event health | Product Platform + ANSVIS Integration | Không | Hiển thị trạng thái camera/task/event delay |
| Attendance/timekeeping business rule | Product Platform | Không | Nhận face event rồi xử lý theo lịch học/ca làm |
| Facial Recognition setup | AI Pipeline + ANSVIS Integration | Không mặc định | Cần consent/enrollment/threshold, không cần train từ đầu |
| Littering/Smoking/Uniform/PPE spec | AI Pipeline | Không | Chốt class/rule/ROI/output trước |
| Baseline/shadow cho 4 pipeline custom | AI Pipeline | Cần camera thật hoặc sample hợp lệ | Dùng model hiện có nếu có thể để đo trước |
| Dataset/label/train/fine-tune | AI Pipeline | Có | Chỉ làm khi baseline/shadow không đạt |
| Notification/report/review queue | Product Platform | Không | Dùng event schema, không phụ thuộc model train xong |

## Task checklist chi tiết cho AI/ANSVIS

| ID | Task | Mục đích | DoD |
|---|---|---|---|
| AI-DATA-01 | Lập ma trận 34 camera/task/ROI/threshold ban đầu | Biết camera nào phục vụ nghiệp vụ nào | Có bảng camera ID, khu vực, task, ROI, schedule, event type |
| AI-DATA-02 | Định nghĩa event schema tối thiểu từ ANSVIS | Tránh nhận raw payload quá rộng | Có schema version, field bắt buộc, field bị cấm log |
| AI-DATA-03 | Cấu hình Facial Recognition dùng chung | Có model/task cho điểm danh và chấm công | Face Detection/Facial Recognition chạy được, threshold/version/rollback rõ |
| AI-DATA-04 | Viết spec Littering Detection pipeline | Làm rõ xả rác là hành vi, không chỉ object detection | Có person/object/tracking/ROI/left-object rule và event output |
| AI-DATA-05 | Viết spec Smoking Detection pipeline | Giảm nhầm lẫn với hành vi tương tự | Có class/signals, confidence, rule `nghi vấn`, human review bắt buộc |
| AI-DATA-06 | Viết spec Student Uniform Detection | Chốt đồng phục theo quy định trường | Có class/rule cho áo/quần/váy/thẻ/logo/giày nếu áp dụng |
| AI-DATA-07 | Viết spec Kitchen PPE Detection | Chốt bảo hộ bếp | Có class/rule cho mũ, khẩu trang, tạp dề, găng tay, đồng phục, giày bảo hộ |
| AI-DATA-08 | Chuẩn bị mock/sanitized event cho backend/app/web | Không cần dữ liệu thật vẫn phát triển được hệ thống | Có payload mẫu đã sanitize cho đủ 6 chức năng |
| AI-DATA-09 | Tạo dataset manifest template cho custom pipeline | Sẵn sàng quản lý dữ liệu nếu phải train/fine-tune | Template có source camera, time range, consent, label, checksum, retention |
| AI-DATA-10 | Tạo quy trình export sample từ ANSVIS | Thu dữ liệu có kiểm soát | Có bước approval, nơi lưu mã hóa, người thực hiện, audit |
| AI-DATA-11 | Tạo data sanitization checklist | Loại dữ liệu không hợp lệ/nhạy cảm không cần thiết | Có checklist trước label/train |
| AI-DATA-12 | Thiết lập quyền truy cập dataset/model | Hạn chế rò rỉ dữ liệu AI | Chỉ người được duyệt có quyền, có audit truy cập/export |
| AI-DATA-13 | Định nghĩa metric theo từng task | Nghiệm thu AI rõ ràng | Có precision/recall/FP/FN/confidence threshold cho từng nhóm |
| AI-DATA-14 | Thiết lập shadow mode rule | Tránh AI tự động gây hậu quả khi chưa đủ tin cậy | Event shadow không gửi thông báo nhạy cảm, có review queue |
| AI-DATA-15 | Tạo model/pipeline registry rule | Biết model/pipeline nào dùng cho task nào | Model/pipeline có version, checksum/config hash, dataset hash nếu có, metric, approval |
| AI-DATA-16 | Tạo rollback/retraining rule | Có đường lui khi model/pipeline lỗi | Có rollback config/model; retrain chỉ dùng sample hợp lệ và phải qua evaluate/shadow |

## Tiêu chí dữ liệu pilot tối thiểu

| Nhóm task | Dữ liệu cần có | Lưu ý nghiệm thu |
|---|---|---|
| Điểm danh/chấm công | Sample người đi qua camera theo các khung giờ, ánh sáng, mật độ khác nhau; dữ liệu khuôn mặt chỉ khi có consent | Ưu tiên kiểm false match, missed match, object-level authorization |
| Đồng phục/bảo hộ | Sample đủ các trường hợp đúng/sai, nhiều góc người, che khuất một phần | Dễ hơn nếu ROI rõ, camera đủ gần |
| Xả rác | Sample hành vi xả rác thật/diễn tập hợp lệ và các hành vi dễ nhầm | Cần kiểm false positive với cúi nhặt đồ/đặt đồ tạm |
| Hút thuốc | Sample cần đủ rõ vì vật thể nhỏ và hay bị che | Rủi ro false negative cao, cần human review |
| Happiness index | Không thuộc baseline sáu chức năng hiện tại | Chỉ nghiên cứu qua change request riêng sau đánh giá privacy/consent và tiêu chí nghiệm thu |

## Tiêu chí nghiệm thu AI theo task

| Task AI | Gate tối thiểu trước production |
|---|---|
| Điểm danh/chấm công | Consent flow hoạt động, shadow mode đạt ngưỡng đã duyệt, có review cho confidence thấp, không gửi sai dữ liệu cho phụ huynh/giáo viên |
| Vi phạm đồng phục/bảo hộ | Có threshold theo camera/ROI, có review hoặc appeal nếu ảnh hưởng kỷ luật |
| Xả rác | False positive được kiểm soát, evidence đủ rõ, notification/report không chứa dữ liệu quá mức |
| Hút thuốc | Không tự động kết luận kỷ luật nếu evidence/confidence thấp, có human review |
| Happiness index | Không áp dụng trong baseline hiện tại; không được làm chậm hoặc chặn sáu chức năng chính |

## Custom training/fine-tune workflow khi cần

| Bước | Output |
|---|---|
| Xác định bài toán | Xả rác, hút thuốc, đồng phục học sinh, PPE/bảo hộ bếp |
| Xác định dữ liệu hợp lệ | Chỉ dữ liệu từ camera dự án qua ANSVIS/AIBOX, kèm consent, phạm vi camera |
| Label | Class list, annotation, review |
| Train | Experiment với FAST/ACCURATE/MOST ACCURATE/CUSTOM nếu dùng ANSTS |
| Evaluate | mAP, precision/recall, false positive/false negative trên dữ liệu ANSVIS/camera đã kiểm soát |
| Export | Model zip/artifact, checksum |
| Register | Model version, dataset hash, metric, approval |
| Deploy shadow | Chạy quan sát, chưa tự động xử lý chính thức |
| Production | Bật sau khi đạt threshold và có rollback |

## HTTP Trigger policy

- Dùng custom payload tối thiểu field cần thiết.
- Ưu tiên media URL private/signed URL, hạn chế base64.
- Validate source, token/HMAC, schema version.
- Idempotency key theo `event_id + camera_id + event_time + event_type`.
- Không append video cho mọi event nếu tải cao; chỉ bật với event cần evidence.
- Tắt debug sau khi test.

## Face recognition policy

- Chỉ dùng khi có consent hợp lệ.
- Không gửi face crop qua notification.
- Không cho phụ huynh/giáo viên export face DB.
- Backend chỉ lưu mapping tối thiểu, không lưu face image nếu không cần.
- Threshold phải được test theo camera thật.
- Nhận diện không chắc chắn phải vào review queue.
