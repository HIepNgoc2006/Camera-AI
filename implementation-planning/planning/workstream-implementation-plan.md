# Workstream implementation plan - Product Platform, ANSVIS Integration và AI Model/Pipeline

## Mục tiêu

File này là bản kế hoạch điều phối chính sau khi đã chốt hướng đi mới.

## Mission hiện tại

Phạm vi triển khai hiện tại được chốt gọn:

- **Xây dựng/hoàn thiện model hoặc pipeline còn thiếu** cho Littering Detection, Smoking Detection, Student Uniform Detection và Kitchen PPE Detection.
- **Phát triển App/Web/Backend** để nhận event từ ANSVIS, quản lý điểm danh/chấm công/vi phạm, dashboard, notification, report, audit và vận hành.
- **Tích hợp ANSVIS** để cấu hình camera/task/model/ROI/rule, nhận HTTP Trigger và theo dõi camera/task/event health.

Sáu chức năng thuộc baseline hiện tại là: điểm danh học sinh, chấm công giáo viên, phát hiện xả rác, phát hiện nghi vấn hút thuốc, phát hiện vi phạm đồng phục học sinh và phát hiện thiếu PPE bếp. Happiness index không thuộc baseline này; nếu phát sinh sẽ được quản lý như change request riêng sau khi có mục đích, consent, tiêu chí nghiệm thu và đánh giá tác động quyền riêng tư.

Không mở rộng sang phần cứng, khảo sát/lắp đặt/căn chỉnh camera hoặc module AI mới ngoài scope đã chốt.

Nguyên tắc quan trọng:

- **Web, Mobile App, Backend, Database là sản phẩm phần mềm chính**. Phần này phải xây được bằng mock/sanitized event, không phụ thuộc việc train xong AI.
- **ANSVIS Integration là cầu nối** giữa camera/ANSVIS và hệ thống phần mềm. Phần này nhận event, validate, normalize, lưu database, hiển thị dashboard và gửi cảnh báo.
- **AI custom pipeline/training là workstream riêng**. Chỉ liên quan đến cấu hình/model/pipeline của ANSVIS cho xả rác, hút thuốc, đồng phục học sinh, PPE bếp. Không để phần này làm chậm việc build Web/App/Backend.
- **Security/privacy là gate chung** cho cả ba luồng trên.

Model/capability chi tiết nằm trong [ansvis-model-capability-matrix.md](ansvis-model-capability-matrix.md). Khi có thay đổi model trên máy ANSVIS, cập nhật file đó trước rồi mới điều chỉnh issue/plan.

## Bức tranh tổng thể

```text
Camera / ANSVIS / AI Task
        |
        | HTTP Trigger / Webhook / Event
        v
ANSVIS Adapter + Event Ingestion
        |
        v
Backend nghiệp vụ + PostgreSQL + Object Storage
        |
        +--> Web Portal quản trị/BGH/GV/Phụ huynh
        +--> Mobile App phụ huynh/GV/BGH
        +--> Notification / Report / Audit / Monitoring
```

## Tách workstream

| Workstream | Mục tiêu | Phụ thuộc training AI không? | Output chính |
|---|---|---:|---|
| Product Platform | Backend, database, Web Portal, Mobile App, auth, phân quyền, báo cáo, cảnh báo | Không | Hệ thống quản lý chạy được bằng mock/sanitized event |
| ANSVIS Integration | Nhận event từ ANSVIS, chuẩn hóa, idempotency, tracking camera/task, health dashboard | Không phụ thuộc train; cần ANSVIS/camera để test thật | ANSVIS Adapter, event contract, camera/task registry |
| AI Model/Pipeline | Facial Recognition có sẵn + 4 custom pipeline: Littering, Smoking, Student Uniform, Kitchen PPE | Có, nhưng là luồng riêng | Pipeline spec, model/config version, shadow report, acceptance metric |
| QA/Security/Ops | Test, UAT, monitoring, backup, incident response, security scan | Không | Gate kiểm thử/nghiệm thu/vận hành |

## Mapping theo video tập huấn ANSVIS/AIBOX

Video tập huấn xác nhận ANSVIS/AIBOX có các màn hình và thao tác nền tảng sau. Các thao tác này phải được đưa vào plan theo đúng workstream, không trộn lẫn thành một task “train AI” chung chung.

| Nội dung trong video | Workstream chịu trách nhiệm | Cách dùng trong dự án | Output cần có |
|---|---|---|---|
| AI Task Configuration, start/stop task, task list | ANSVIS Integration + AI Pipeline | Quản lý task cho điểm danh, chấm công, xả rác, hút thuốc, đồng phục, PPE bếp | AI Task configuration sheet |
| Camera Configuration, IP/simulated camera | ANSVIS Integration | Nhận camera/RTSP/ONVIF do bên phần cứng bàn giao và ánh xạ vào camera registry | Camera connection matrix, stream health report |
| Face Recognition Service, user/group/face recording | AI Pipeline + Security | Dùng cho điểm danh/chấm công, nhưng chỉ khi có consent và quy trình enrollment | Face enrollment SOP, consent gate, low-confidence review |
| ROI/rule/threshold/tracker | AI Pipeline | Giảm false positive cho từng nghiệp vụ, đặc biệt xả rác/hút thuốc/PPE/đồng phục | ROI/rule/threshold version theo camera/task |
| Event Log Management | ANSVIS Integration + QA | Đối soát event ANSVIS với event backend, hỗ trợ debug/shadow mode | Event reconciliation report |
| HTTP Trigger/API JSON | ANSVIS Integration | Gửi event từ ANSVIS sang Backend qua endpoint riêng | Event contract, Adapter, contract test |
| Storage/cloud/upload/export | Security/Ops | Kiểm soát ảnh/video/event export, không lộ dữ liệu học sinh/face DB | Evidence policy, retention, audit log |
| Model Management, upload model zip | AI Pipeline + Ops | Theo dõi model có sẵn/custom, version, rollback | Model/pipeline registry |

Quy tắc đọc video:

- Video là tài liệu thao tác ANSVIS, không phải SRS/API spec hoàn chỉnh.
- Video không chứng minh đủ model production cho 4 nghiệp vụ custom.
- Các màn hình ANSVIS phải được chuyển thành checklist vận hành, event contract và acceptance gate.
- Mọi dữ liệu face/event/media trong ANSVIS được xem là dữ liệu nhạy cảm và phải qua security/privacy gate.

## Workstream 1 - Product Platform

Đây là phần phải build trước và không được dính trực tiếp vào quá trình train AI.

### Phạm vi

| Module | Nội dung |
|---|---|
| Identity/Auth | User, role, session, MFA admin/BGH, refresh/revoke token |
| School data | Học sinh, phụ huynh, giáo viên, lớp, phân công |
| Consent | Đồng ý/rút đồng ý xử lý dữ liệu sinh trắc học |
| Attendance | Có mặt, vắng mặt, đi muộn, check-in/check-out |
| Timekeeping | Giờ vào/ra, đi muộn, về sớm, ngày công, báo cáo tháng |
| Violation | Sự kiện vi phạm, trạng thái review, correction/appeal |
| Notification | In-app/push/email policy, không gửi media nhạy cảm trong push |
| Report/Export | Dashboard, thống kê, export có audit |
| Evidence | Metadata ảnh/video, private object storage, signed URL |
| Audit | Ghi vết xem/sửa/xóa/export dữ liệu nhạy cảm |

### Input để build

- Mock/sanitized ANSVIS event.
- OpenAPI schema.
- Role/permission matrix.
- Database schema.
- UI flow.

### Output

- Backend API chạy được.
- Web Portal chạy được.
- Mobile App chạy được.
- PostgreSQL schema/migration.
- Test auth/permission/object-level authorization.
- Dashboard có thể hiển thị dữ liệu giả lập.

### Không thuộc workstream này

- Train model.
- Label dataset.
- Tối ưu mAP/precision/recall của model.
- Export face DB/dataset thật.

## Workstream 2 - ANSVIS Integration

Workstream này là phần kết nối giữa ANSVIS và hệ thống phần mềm.

### Phạm vi

| Hạng mục | Nội dung |
|---|---|
| Camera registry | Camera ID/name, khu vực, nhóm nghiệp vụ, credential reference |
| ANSVIS task registry | Task name, model, ROI, threshold, schedule, version |
| HTTP Trigger contract | Payload tối thiểu, schema version, event type, confidence |
| ANSVIS Adapter | Nhận webhook, auth/source validation, normalize event |
| Event ingestion | Idempotency, queue/outbox, retry, DLQ |
| Evidence policy | Ảnh/video chỉ lưu khi cần, private URL/signed URL |
| Health monitoring | Camera online/offline, task running/stopped, event delay |
| Integration dashboard | Web screen theo dõi camera/task/event health |

### Các bước triển khai theo ANSVIS video

| Bước | Việc làm | Không làm lẫn vào bước này |
|---|---|---|
| INT-01 | Xác nhận version ANSVIS, license, GPU, model list, task/channel limit | Không cam kết AI accuracy |
| INT-02 | Lập camera registry và mapping camera -> khu vực -> nghiệp vụ | Không làm khảo sát/lắp đặt vật lý |
| INT-03 | Cấu hình 1-3 camera mẫu hoặc simulated camera trong ANSVIS | Không mở 34 camera cùng lúc |
| INT-04 | Tạo HTTP Trigger test về backend staging/mock endpoint | Không để token/debug payload trong log |
| INT-05 | Chuẩn hóa event contract tối thiểu cho 6 chức năng | Không để Web/App phụ thuộc raw ANSVIS payload |
| INT-06 | Xây ANSVIS Adapter validate/auth/normalize/idempotency | Không xử lý business rule trực tiếp trong ANSVIS |
| INT-07 | Đối soát Event Log ANSVIS với event backend | Không dùng Event Storage của ANSVIS làm source of truth |
| INT-08 | Mở rộng theo nhóm camera và benchmark tải | Không rollout toàn bộ nếu chưa có health/performance baseline |

### Event flow chuẩn

```text
ANSVIS HTTP Trigger
  -> API Gateway
  -> ANSVIS Adapter
  -> Validate source/auth/schema/size
  -> Normalize event
  -> Idempotency check
  -> Event Ingestion
  -> Queue/Outbox
  -> Attendance / Timekeeping / Violation / Notification / Report
```

### Event type cần chuẩn hóa

| Event group | Event từ ANSVIS/pipeline | Backend xử lý |
|---|---|---|
| Face attendance | Face recognized / unknown / low confidence | Attendance/Timekeeping |
| Littering | Suspected littering | Violation review |
| Smoking | Suspected smoking | Violation review bắt buộc |
| Student uniform | Uniform correct/incorrect/unknown | Violation review |
| Kitchen PPE | Missing PPE component | Violation review |
| Camera/task health | Camera offline, task stopped, event delay | Ops alert/dashboard |

### Output

- ANSVIS event contract.
- Sanitized payload fixtures.
- Adapter service.
- Contract tests.
- Camera/task status dashboard.
- Runbook cấu hình HTTP Trigger.

## Workstream 3 - AI Model/Pipeline

Workstream này tách riêng khỏi Web/App/Backend. Product Platform vẫn build bình thường bằng mock event trong khi AI pipeline được thiết kế/test riêng.

Không được coi “train AI” là một task duy nhất. Với mỗi nghiệp vụ AI, thứ tự đúng là:

```text
Pipeline spec
  -> baseline bằng model/rule hiện có trong ANSVIS nếu có
  -> shadow mode
  -> đánh giá FP/FN và threshold
  -> custom train/fine-tune nếu baseline không đạt
  -> import/register model/config
  -> shadow lại
  -> production rollout có rollback
```

### Model/pipeline scope

| Chức năng | Model/pipeline | Hướng làm |
|---|---|---|
| Điểm danh học sinh | Facial Recognition | Dùng Face Detection/Facial Recognition có sẵn trong ANSVIS |
| Chấm công giáo viên | Facial Recognition | Dùng chung nền tảng face, khác rule backend |
| Xả rác | Littering Detection | Custom pipeline/model/rule |
| Hút thuốc | Smoking Detection | Custom pipeline/model/rule, trả `nghi vấn`, cần human review |
| Đồng phục học sinh | Student Uniform Detection | Custom model/pipeline theo quy định đồng phục |
| PPE bếp | Kitchen PPE Detection | Custom model/pipeline theo rule bảo hộ |

### Thứ tự AI nên làm

| Thứ tự | Hạng mục | Lý do |
|---|---|---|
| 1 | Facial Recognition cho điểm danh/chấm công | Có model sẵn, backend/rule là chính |
| 2 | Kitchen PPE | Khu vực rõ, rule rõ |
| 3 | Student Uniform | Cần chốt quy định đồng phục |
| 4 | Littering | Cần tracking và dữ liệu video thực tế |
| 5 | Smoking | Khó nhất, dễ false positive |

### Quy trình cho từng custom pipeline

| Bước | Nội dung | Output |
|---|---|---|
| Spec | Chốt class, rule, ROI, event output, human review | Pipeline spec |
| Baseline | Thử model có sẵn như GenericOD/Object/Helmet nếu phù hợp | Baseline report |
| Shadow | Chạy quan sát, không tự động kết luận | Shadow report |
| Dataset nếu cần | Thu sample từ camera/ANSVIS theo consent và manifest | Dataset manifest |
| Label/train nếu cần | Label và train/fine-tune bằng ANSTS hoặc công cụ được duyệt | Model artifact |
| Evaluate | Đo FP/FN, precision/recall, lỗi thường gặp | Metric report |
| Deploy | Thay model/config có version và rollback | Production candidate |

Checklist bắt buộc áp dụng cho GitHub Issues #99-#102:

1. Chốt class, rule nghiệp vụ, ROI, event output và tình huống không đủ căn cứ kết luận.
2. Kiểm tra capability/model hiện có trên đúng phiên bản ANSVIS đang sử dụng.
3. Chạy baseline bằng model/rule hiện có trước khi quyết định train.
4. Cấu hình ROI, threshold, tracker, schedule và version cấu hình.
5. Chạy shadow mode; chưa gửi cảnh báo kỷ luật tự động.
6. Đo precision, recall, false positive, false negative, latency và chất lượng evidence.
7. Chỉ tạo dataset/label/train/fine-tune khi baseline không đạt ngưỡng đã định.
8. Đăng ký dataset hash, model/config version, metric, người kiểm tra và trạng thái phê chuẩn kỹ thuật.
9. Import model/config vào ANSVIS và chạy shadow mode lại.
10. Thực hiện human review, acceptance và kiểm tra đường rollback/disable.

### Quy tắc dữ liệu AI

- Dataset thật không nằm trong Git.
- Dataset chỉ lấy từ camera dự án qua ANSVIS/AIBOX.
- Không dùng dataset ngoài/trường khác/Internet nếu chưa có phê duyệt riêng.
- Face image/face DB là dữ liệu Critical.
- Mọi model/config/pipeline phải có version, metric, reviewer, approval.

## Workstream 4 - QA, Security, Ops

### QA

| Nhóm test | Mục tiêu |
|---|---|
| Unit test | Business rule attendance/timekeeping/violation |
| Contract test | ANSVIS payload schema, invalid payload, duplicate event |
| Permission test | Parent chỉ xem con mình, teacher chỉ xem lớp mình |
| E2E test | Login -> event -> dashboard/app -> notification/report |
| Shadow test | AI event chưa tự động kết luận khi chưa nghiệm thu |
| UAT | Nhà trường xác nhận từng module |

### Security gate

| Gate | Bắt buộc |
|---|---|
| Consent | Block biometric nếu thiếu consent |
| RBAC/ABAC | Object-level authorization |
| Secret | Không `.env` thật trong Git, secret manager cho staging/prod |
| Log masking | Không log face/base64/token/RTSP credential |
| Evidence | Private storage, signed URL ngắn hạn |
| Webhook | Token/HMAC/source validation, body size limit |
| Audit | Xem/sửa/xóa/export dữ liệu nhạy cảm |

### Ops

| Hạng mục | Nội dung |
|---|---|
| Monitoring | API, queue, DB, storage, ANSVIS task, camera status |
| Backup/restore | PostgreSQL, object storage, ANSVIS config/model/face DB nếu được phép |
| Incident response | Rò rỉ dữ liệu, sai phân quyền, event giả, webhook flood |
| Rollback | App release, DB migration, model/config ANSVIS |

## Thứ tự triển khai tổng thể

| Thứ tự | Việc làm | Workstream | Ghi chú |
|---|---|---|---|
| 1 | Chốt SRS, role, data class, consent, acceptance | Product + Security | Không cần dataset thật |
| 2 | Scaffold monorepo, Docker Compose, CI, secret scan | Product Platform | Không liên quan train |
| 3 | Backend core: auth, school, consent, audit, database | Product Platform | Dùng fake data |
| 4 | ANSVIS event contract + mock payload + adapter skeleton | ANSVIS Integration | Dùng sanitized fixture |
| 5 | Web Portal skeleton + dashboard/report/review screens | Product Platform | Dùng mock event |
| 6 | Mobile App skeleton + auth/attendance/notification | Product Platform | Dùng mock API |
| 7 | Facial Recognition integration cho attendance/timekeeping | ANSVIS Integration + AI | Dùng model có sẵn |
| 8 | Model capability gate và spec 4 custom pipelines | AI Model/Pipeline | Đối chiếu `ansvis-model-capability-matrix.md`, chưa train ngay |
| 9 | Tích hợp camera thật/staging/pilot | ANSVIS Integration | Bắt đầu shadow mode |
| 10 | Build/test custom pipeline theo thứ tự PPE -> uniform -> littering -> smoking | AI Model/Pipeline | Có thể train nếu baseline không đạt |
| 11 | E2E, security hardening, performance benchmark | QA/Security/Ops | Không còn lỗi Critical/High |
| 12 | UAT, đào tạo, go-live, support | Tất cả | Có runbook/rollback |

## Cách theo dõi trên GitHub Issues

| Nhóm issue | Dùng để theo dõi |
|---|---|
| Backend/Web/Mobile | Product Platform |
| `area:ansvis` | ANSVIS Integration |
| `area:ai-model` | AI custom pipeline/training |
| `area:security`, `risk:*` | Security gate |
| `area:qa` | Test/UAT/acceptance |
| `area:devops` | Deploy/monitoring/backup |

Các issue AI quan trọng:

- #90 - 34-camera task mapping matrix.
- #92 - Per-pipeline AI acceptance metrics.
- #98 - Facial Recognition for attendance/timekeeping.
- #99 - Littering Detection custom pipeline.
- #100 - Smoking Detection custom pipeline.
- #101 - Student Uniform Detection custom pipeline.
- #102 - Kitchen PPE Detection custom pipeline.

## Definition of Ready trước khi code

Definition of Ready được áp dụng theo hai tầng để không chặn các biện pháp bảo vệ repository nhưng vẫn chặn business code khi đầu vào chưa đủ:

### Tầng A - Repository/codebase foundation

- Được phép làm: `.gitignore`, `.env.example`, monorepo skeleton, lint/test scaffold, CI và secret scan.
- Chỉ dùng placeholder/fake data; không cần credential, camera thật, payload thật hoặc dataset thật.
- Chưa được bật biometric processing hoặc tích hợp production.

### Tầng B - Business/ANSVIS/Web/Mobile implementation

- Có mock/sanitized ANSVIS payload cho 6 chức năng.
- Có role/permission matrix.
- Có data classification và consent rule.
- Có database/encryption plan.
- Có API/event contract baseline.
- Có GitHub Issues theo workstream.
- Không cần dataset thật để bắt đầu build Product Platform.

Checkpoint 2026-07-13: Tầng A được phép bắt đầu. Tầng B chưa đạt vì role/permission matrix, OpenAPI/event contract baseline và mock/sanitized fixture chưa có artifact hoàn chỉnh; các issue liên quan phải giữ trạng thái blocked/not-ready cho đến khi có evidence.

## Kết luận

Hướng triển khai sau khi tách workstream:

```text
Build Web/App/Backend trước bằng mock event
  -> tích hợp ANSVIS event thật
  -> theo dõi camera/task/event trên dashboard
  -> chạy Facial Recognition có sẵn
  -> thiết kế/test 4 custom pipelines
  -> train/fine-tune chỉ khi pipeline baseline không đạt
```
