# ANSVIS model capability matrix - model đã có, còn thiếu và hướng xử lý

## Mục tiêu

File này chốt lại năng lực ANSVIS/AIBOX sau khi xem lại video tập huấn và đối chiếu với màn hình `Model Management - Server List` hiện tại.

Mục đích là tránh hai hiểu nhầm:

- Không phải mọi chức năng đều cần train AI từ đầu.
- Cũng không phải ANSVIS model hiện có đã đủ cho toàn bộ 6 chức năng của dự án.

## Kết luận ngắn

| Hạng mục | Kết luận |
|---|---|
| Điểm danh học sinh | Có thể bắt đầu bằng `Face Detection` + `Facial Recognition` có sẵn |
| Chấm công giáo viên/cán bộ | Dùng chung `Face Detection` + `Facial Recognition`, khác rule backend |
| Xả rác | Chưa có model/pipeline hoàn chỉnh trên màn hình hiện tại; cần custom pipeline |
| Hút thuốc | Có `ANS_FireSmoke`, nhưng không đủ để kết luận hút thuốc; cần custom Smoking Detection pipeline |
| Đồng phục học sinh | Chưa có model đồng phục học sinh; cần custom Student Uniform Detection |
| PPE/bảo hộ bếp | Có `ANS_Helmet` làm tham khảo nhưng thiếu nhiều class bếp; cần custom Kitchen PPE Detection |

Điểm cần khóa lại trong plan: video tập huấn xác nhận **cách cấu hình nền tảng ANSVIS**, không xác nhận rằng các model hiện có đã đủ tiêu chuẩn production cho toàn bộ bài toán trường học. Vì vậy mọi pipeline ngoài Facial Recognition đều phải qua capability gate và shadow mode.

## Video tập huấn xác nhận được gì

Video cho thấy ANSVIS/AIBOX hỗ trợ các nhóm thao tác sau:

| Nhóm thao tác | Có trong video | Ý nghĩa với dự án |
|---|---:|---|
| Thêm camera/nguồn video | Có | Cấu hình camera IP/RTSP/ONVIF hoặc simulated camera |
| Tạo AI Task | Có | Mỗi nghiệp vụ cần task riêng hoặc task group riêng |
| Chọn model/class | Có | Dùng model có sẵn hoặc model custom nếu cần |
| ROI/rule/threshold | Có | Giảm false positive bằng vùng quan sát, rule, confidence |
| Face Recognition | Có | Cơ sở cho điểm danh/chấm công |
| Event Log | Có | Nguồn đối soát event AI |
| HTTP Trigger/API | Có | Gửi event sang Backend |
| Export/import event/dataset | Có một phần | Dùng cho debug/feedback loop/custom training nếu cần |
| Server/GPU/license/storage | Có | Cần kiểm capacity trước rollout 34 camera |

Video chủ yếu là hướng dẫn cấu hình/vận hành ANSVIS. Video không tự thay thế được tài liệu SRS, event contract, security, UAT, hoặc model acceptance.

## Model hiện có trên máy ANSVIS

Theo ảnh chụp màn hình `Model Management - Server List`, máy hiện có:

| Model | Version | Type | Categories/khả năng liên quan | Đánh giá dùng cho dự án |
|---|---|---|---|---|
| `Face Detection` | v1.0 | FACEDETECTOR | N/A | Dùng cho phát hiện khuôn mặt |
| `Facial Recognition` | v1.1 | FACERECOGNIZER | Registered Faces: 92 | Dùng cho điểm danh/chấm công, phải kiểm consent/face DB |
| `ANS_GenericOD(GPU)` | v1.0 | DETECTION | 80 class COCO như person, car, chair, bottle... | Dùng baseline person/object; không đủ cho uniform/smoking/littering logic |
| `ANS_Objects` | v2.0 | DETECTION | 18 class như umbrella, cart, vegetable, flower, egg, sign, garbage, chair, table, box, basket, bucket, car, motorbike, bus, truck, bike, transport | Có class `garbage` nhưng chưa đủ thành hành vi xả rác |
| `ANS_Helmet` | v2.0 | DETECTION | license_plate, motorcyclist, helmet, no_helmet | Có thể tham khảo PPE/headwear nhưng không đủ PPE bếp |
| `ANS_FireSmoke` | v2.0 | DETECTION | fire, fake_fire, smoke, fake_smoke | Có thể hỗ trợ phát hiện khói, không đủ xác định hút thuốc |
| `ANS_VehicleDetection` | v2.0 | DETECTION | car, motorbike, bus, truck, bike, container, tricycle, human | Không thuộc 6 chức năng chính |
| `OCR` | v2.0 | TEXTSCENE | N/A | Không thuộc 6 chức năng chính |
| `License Plate Recognition(VN)` | v1.4 | LICENSEPLATE | N/A | Không thuộc 6 chức năng chính |
| `ANS_Pet` | v2.0 | DETECTION | pet | Không thuộc 6 chức năng chính |

## Matrix 6 chức năng

| Chức năng | Model có thể dùng ngay | Cần custom không? | Backend/Web/App có cần chờ custom AI không? | Ghi chú |
|---|---|---:|---:|---|
| Điểm danh học sinh | Face Detection + Facial Recognition | Không mặc định | Không | Backend xử lý lịch học, lớp, có mặt/vắng/đi muộn/check-in/check-out |
| Chấm công giáo viên | Face Detection + Facial Recognition | Không mặc định | Không | Backend xử lý ca làm, giờ vào/ra, về sớm, báo cáo tháng |
| Xả rác | GenericOD/Objects có thể làm baseline | Có | Không | Cần pipeline hành vi: person/object tracking, vùng bỏ rác, vật bị bỏ lại |
| Hút thuốc | FireSmoke chỉ hỗ trợ một phần nếu có khói | Có | Không | Cần pipeline nghi vấn hút thuốc; bắt buộc human review |
| Đồng phục học sinh | Chưa có model phù hợp | Có | Không | Cần chốt quy định đồng phục trước khi model/rule |
| PPE/bảo hộ bếp | Helmet có thể tham khảo một phần | Có | Không | Cần class mũ, khẩu trang, tạp dề, găng tay, đồng phục bếp, giày |

## Quyết định triển khai theo capability

### Nhóm có thể triển khai trước bằng model có sẵn

| Nhóm | Làm ngay được | Cần bổ sung |
|---|---|---|
| Face attendance/timekeeping | Cấu hình Face Detection, Facial Recognition, group/person, threshold, event trigger | Consent, enrollment workflow, backend rule, low-confidence review |

### Nhóm cần custom pipeline/model-rule

| Pipeline | Có thể tận dụng model hiện có | Phần còn thiếu |
|---|---|---|
| Littering Detection | `person` từ GenericOD, `garbage` từ ANS_Objects nếu đủ | Tracking, left-object logic, allowed trash zone, false-positive review |
| Smoking Detection | `smoke` từ ANS_FireSmoke nếu camera đủ gần | Cigarette/vape, hand-to-mouth pattern, suspected-smoking rule |
| Student Uniform Detection | Có thể dùng `person` baseline | Uniform classes, student card/logo/color, school-specific rule |
| Kitchen PPE Detection | `helmet/no_helmet` từ ANS_Helmet nếu phù hợp | Hair cover, mask, apron, gloves, kitchen uniform, safety shoes |

Các dòng “có thể tận dụng” chỉ có nghĩa là dùng để thử baseline. Chúng không được dùng làm cam kết nghiệm thu nếu chưa có metric, shadow report và approval.

## Plan điều chỉnh theo model có/chưa có

| Giai đoạn | Mục tiêu | Việc làm | Không làm trong giai đoạn này |
|---|---|---|---|
| Model Capability Gate | Chốt model nào có sẵn, model nào thiếu | Kiểm ANSVIS model list, license, GPU, task limit, class list | Không train ngay |
| Product Build | Build Backend/Web/Mobile độc lập | Dùng mock/sanitized event cho đủ 6 chức năng | Không chờ dataset/custom AI |
| ANSVIS Integration | Tạo HTTP Trigger, event contract, adapter, camera/task dashboard | Test bằng model có sẵn và mock payload | Không xử lý business rule trong ANSVIS |
| Face Recognition Pilot | Cấu hình điểm danh/chấm công | Enrollment, threshold, known/unknown, backend attendance/timekeeping | Không dùng face nếu thiếu consent |
| Custom Pipeline Spec | Làm rõ 4 pipeline còn thiếu | Spec class/rule/ROI/event/metric/human review | Không train khi chưa có spec |
| Baseline/Shadow | Thử model hiện có làm baseline | Chạy shadow mode, đo sai/đúng, chỉnh threshold/ROI | Không kết luận kỷ luật tự động |
| Custom Train/Fine-tune nếu cần | Bù phần model hiện có không đáp ứng | Dataset manifest, label, train/evaluate, import model, shadow lại | Không dùng dataset ngoài nếu chưa duyệt |

## Issue mapping

| Nội dung | GitHub Issue |
|---|---|
| Mapping 34 camera/task/ROI/threshold | #90 |
| Metric nghiệm thu từng model/pipeline | #92 |
| Facial Recognition điểm danh/chấm công | #98 |
| Littering Detection custom pipeline | #99 |
| Smoking Detection custom pipeline | #100 |
| Student Uniform Detection custom pipeline | #101 |
| Kitchen PPE Detection custom pipeline | #102 |

## Rủi ro cần ghi nhớ

| Rủi ro | Mức | Cách xử lý |
|---|---:|---|
| Tưởng có `garbage` là đủ phát hiện xả rác | Cao | Xem xả rác là hành vi, cần tracking/rule/human review |
| Tưởng `smoke` là đủ phát hiện hút thuốc | Cao | Chỉ trả `nghi vấn`, cần người xác nhận |
| Tưởng `helmet/no_helmet` là đủ PPE bếp | Cao | PPE bếp có nhiều thành phần khác mũ |
| Facial Recognition có 92 registered faces nhưng chưa rõ consent | Rất cao | Không export/đụng face DB thật nếu chưa có phê duyệt |
| Web/App bị chờ train AI | Cao | Build bằng mock/sanitized event trước |

## Kết luận

Hướng triển khai đúng sau khi xem lại video và model list:

```text
ANSVIS có đủ nền tảng cấu hình camera, task, model, rule, event, HTTP trigger.
Face Detection/Facial Recognition có thể dùng cho điểm danh/chấm công.
4 nghiệp vụ vi phạm còn lại phải đi theo pipeline riêng.
Web/App/Backend không phụ thuộc vào việc train xong các pipeline đó.
```
