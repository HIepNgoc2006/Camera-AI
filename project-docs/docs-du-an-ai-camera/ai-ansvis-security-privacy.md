# AI, ANSVIS, security and privacy

## Mục tiêu

Tài liệu này gom các nội dung AI/ANSVIS/AIBOX, training model, bảo mật, privacy và consent. Đây là phần quan trọng nhất vì hệ thống xử lý dữ liệu trẻ em và dữ liệu sinh trắc học.

## Vai trò ANSVIS/AIBOX

ANSVIS/AIBOX xử lý camera/video, chạy AI Task, tạo Event Log và gửi event về Backend qua HTTP Trigger hoặc cơ chế tích hợp được duyệt. Backend không nên tự xử lý trực tiếp toàn bộ RTSP nếu ANSVIS đã là tầng AI chính.

Nguồn yêu cầu kỹ thuật cần bám theo:

- https://doc.anscenter.com.au/
- ANSVIS Introduction, Camera, AI Task, HTTP Trigger, Event Log, Facial Recognition Service.
- ANSTS Introduction, Labelling, Model Training, Evaluate/Export.

## Cấu hình AI Task

| Nhóm | Cần cấu hình |
|---|---|
| Camera | Camera ID/name, RTSP/ONVIF mapping, khu vực |
| AI Task | Loại task, model, threshold, schedule |
| Detection zone | ROI, line/polygon/area nếu cần |
| Trigger | HTTP endpoint, payload type, media policy |
| Event | Event type, confidence, object metadata |
| Monitoring | Task status, process time, interval, error |

Mọi thay đổi threshold/model/ROI phải có version hoặc ghi nhận thay đổi.

## AI workflow

Theo tài liệu ANSCENTER, ANSVIS/AIBOX đã có cơ chế thêm camera, tạo AI Task, chọn model, cấu hình ROI/rule/threshold, sinh Event Log và gửi event sang hệ thống ngoài qua HTTP Trigger. Vì vậy phạm vi mặc định của dự án là **tích hợp và vận hành ANSVIS**, không phải tự train AI từ đầu.

Với phạm vi hiện tại, ANSVIS có sẵn `Face Detection` và `Facial Recognition`, có thể dùng cho điểm danh học sinh và chấm công giáo viên/cán bộ. Bốn phần còn lại gồm xả rác, hút thuốc, đồng phục học sinh và PPE/bảo hộ bếp là các pipeline/model đặc thù hơn; cần được thiết kế, shadow mode và nghiệm thu riêng.

Training/fine-tune bằng ANSTS là phương án triển khai cho các pipeline đặc thù nếu model/task có sẵn không đáp ứng đủ nghiệp vụ. Nếu có training/fine-tune, dữ liệu chỉ lấy từ camera của dự án thông qua ANSVIS/AIBOX, không dùng dataset ngoài nếu chưa có phê duyệt riêng.

## Phân nhóm chức năng AI

| Nhóm | Chức năng | Model/pipeline | Hướng xử lý |
|---|---|---|---|
| Nhóm 1 - Nhận diện khuôn mặt/chấm công | Điểm danh học sinh | Facial Recognition dùng chung | Dùng model có sẵn; backend xử lý lớp, lịch, có mặt/vắng/đi muộn/check-in/check-out |
| Nhóm 1 - Nhận diện khuôn mặt/chấm công | Chấm công giáo viên/cán bộ | Facial Recognition dùng chung | Dùng model có sẵn; backend xử lý ca làm, giờ vào/ra, đi muộn, về sớm, ngày công |
| Nhóm 2 - Hành vi vi phạm | Xả rác | Littering Detection pipeline | Custom pipeline/model/rule; cần tracking và logic vật bị bỏ lại |
| Nhóm 2 - Hành vi vi phạm | Hút thuốc | Smoking Detection pipeline | Custom pipeline/model/rule; trả kết quả `nghi vấn hút thuốc`, cần người xác nhận |
| Nhóm 3 - Đồng phục/PPE | Đồng phục học sinh | Student Uniform Detection | Custom model/pipeline; cần chốt quy định đồng phục |
| Nhóm 3 - Đồng phục/PPE | Bảo hộ bếp | Kitchen PPE Detection | Custom model/pipeline; kiểm mũ, khẩu trang, tạp dề, găng tay, đồng phục, giày bảo hộ |

Kế hoạch triển khai theo hướng mới:

| Bước | Nội dung | Điều kiện đạt |
|---|---|---|
| 1. Mapping camera/task | Gán 34 camera vào từng nhóm nghiệp vụ, ROI, schedule, event type | Có bảng mapping được xác nhận |
| 2. Cấu hình Facial Recognition | Dùng Face Detection/Facial Recognition cho điểm danh và chấm công | ANSVIS sinh event nhận diện khuôn mặt có kiểm soát |
| 3. Thiết kế 4 custom pipeline | Xả rác, hút thuốc, đồng phục học sinh, PPE bếp | Có spec class/rule/ROI/event/metric/human review |
| 4. Chuẩn bị Backend/Web/Mobile | Xây API nhận event, database, audit, consent, dashboard, app notification bằng mock/sanitized event | Hệ thống chạy E2E trước khi có dataset thật |
| 5. Tích hợp camera tại trường | Camera gửi luồng vào ANSVIS, ANSVIS sinh event theo task đã cấu hình | Event đúng schema, không lộ dữ liệu nhạy cảm |
| 6. Shadow mode/hiệu chỉnh | Chạy quan sát, chỉnh ROI/threshold/rule, chưa tự động kết luận sự kiện nhạy cảm | Có thống kê sai/đúng và threshold đề xuất |
| 7. Custom training nếu cần | Thực hiện cho pipeline chưa đạt hoặc thiếu class | Dataset từ ANSVIS/camera có manifest, model có metric/approval |
| 8. Nghiệm thu AI task/pipeline | Duyệt từng task AI trước production | Có biên bản hoặc checklist nghiệm thu |
| 9. Production rollout | Bật từng nhóm camera/task có rollback | Có monitoring, audit, rollback model/task |

| Bước | Output |
|---|---|
| Xác định bài toán | Xả rác, hút thuốc, đồng phục học sinh, PPE/bảo hộ bếp nếu cần custom |
| Xác định dữ liệu hợp lệ | Camera dự án qua ANSVIS/AIBOX, consent, phạm vi camera |
| Label | Class list, annotation, review |
| Train/fine-tune | Experiment, metric, mAP/precision/recall |
| Evaluate | Test trên dataset/video/camera thử nghiệm đã trích xuất hợp lệ từ ANSVIS |
| Export | Model artifact, checksum |
| Register | Model version, dataset hash, reviewer |
| Shadow mode | Chạy quan sát trước production |
| Production | Bật chính thức khi đạt tiêu chí và có rollback |

## AI data safety

Không được:

- Commit dataset, ảnh mặt, video camera, face DB, event JSON thật vào Git.
- Dùng tên thật học sinh trong dataset folder.
- Gửi dataset thật lên dịch vụ ngoài khi chưa được duyệt.
- Tự ý dùng dataset ngoài/Internet/trường khác để train hoặc benchmark model.
- Log raw payload có ảnh/base64/face data.
- Bật ANSVIS debug mode ở production.
- Export face DB/Event Log không có ticket/audit.

Phải làm:

- Dataset dùng mã định danh giả.
- Dataset có manifest, checksum, nguồn camera/ANSVIS, consent status, retention.
- Model có version, metric, dataset hash, reviewer.
- Event nhạy cảm cần human review nếu confidence thấp.
- Có rollback model.

## Security controls

| Nhóm | Kiểm soát |
|---|---|
| Identity | Tài khoản cá nhân, MFA cho Admin/BGH/vận hành |
| Authorization | RBAC/ABAC, object-level authorization |
| API | TLS, rate limit, CORS allowlist, schema validation |
| Webhook ANSVIS | Token/HMAC/source validation, idempotency |
| Data | Encryption at rest, private storage, signed URL |
| Secret | Secret manager, không hard-code, không commit `.env` |
| Audit | Xem/sửa/xóa/export dữ liệu nhạy cảm |
| Monitoring | Alert login fail, export spike, ANSVIS task stop |

## Consent/privacy

Nếu dùng dữ liệu sinh trắc học:

- Phải có consent hợp lệ.
- Thiếu consent thì block xử lý biometric.
- Consent change phải có audit.
- Cần có cơ chế rút consent/deactivate.
- Chỉ xử lý đúng mục đích đã thông báo.

## Data retention đề xuất

| Dữ liệu | Retention tham khảo |
|---|---:|
| Event metadata | Theo chính sách nhà trường |
| Snapshot điểm danh | 30-90 ngày |
| Snapshot vi phạm | 30-180 ngày |
| Video clip sự kiện | 7-30 ngày mặc định |
| Dataset raw | Chỉ giữ khi còn mục đích rõ |
| Model artifact | Giữ theo version/rollback |
| Face DB | Theo consent và chính sách đã duyệt |

## Incident response

Khi nghi ngờ rò rỉ dữ liệu:

1. Ghi nhận thời gian, phạm vi, loại dữ liệu.
2. Cô lập nguồn rò rỉ: revoke token, tắt endpoint, khóa bucket.
3. Bảo toàn evidence: request ID, audit log, event ID.
4. Đánh giá ảnh hưởng.
5. Khắc phục và rotate secret nếu cần.
6. Thông báo nhà trường/phụ huynh theo quy trình đã thống nhất.
7. Postmortem và cập nhật kiểm soát.
