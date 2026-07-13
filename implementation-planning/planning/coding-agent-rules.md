# Coding, agent rules and maintainability guide

## Mục tiêu

File này là guide chi tiết cho developer/AI agent trước khi bắt đầu code hệ thống AI Camera trường học. Root `AGENTS.md` là bản rule bắt buộc để agent đọc tự động; file này giải thích kỹ hơn cách suy nghĩ, cách code, cách test và cách tránh lỗi bảo mật.

Nguyên tắc: code không chỉ cần chạy được. Code phải đúng yêu cầu, bảo mật, dễ đọc, dễ bảo trì, có test, có audit và có thể bàn giao cho người khác.

## Tài liệu phải đọc trước khi code

| Khi làm việc | Phải đọc |
|---|---|
| Bất kỳ task nào | `README.md`, `AGENTS.md`, `planning-index.md`, `workstream-implementation-plan.md` |
| Kiến trúc/service/database | `architecture-stack.md` |
| Database, encryption, backup, retention | `database-and-encryption-plan.md` |
| Security/privacy/secret | `security-privacy-plan.md` |
| AI/ANSVIS/AIBOX/model | `ai-ansvis-plan.md`, `references/Tong-hop-video-TAP-HUAN-CAMERA-AIBOX.md` |
| QA/test/release | `delivery-quality-plan.md`, `operations-tracking-plan.md` |
| Rủi ro | `risk-assessment.md` |
| Chống lan man/scope creep | `agent-scope-control-rules.md`, `requirements-issues-traceability-audit.md` |
| Yêu cầu khách hàng | bộ docs trong `project-docs/docs-du-an-ai-camera/` |

## Hard rules cho agent

Agent không được:

- Đọc, in, paste hoặc tóm tắt giá trị thật trong `.env`.
- Commit `.env`, key, token, license, service account, database dump, face DB export.
- Hard-code secret trong code/test/docs.
- Tạo seed/demo bằng tên học sinh, ảnh học sinh, phụ huynh hoặc dữ liệu thật.
- Log ảnh mặt, face embedding, base64 image, raw biometric payload, token, password, RTSP credential.
- Bỏ qua phân quyền vì “test nhanh”.
- Cho Web/Mobile gọi trực tiếp service nội bộ bỏ qua API Gateway.
- Cho service đọc database schema của service khác.
- Tự thêm task phần cứng/lắp đặt camera vào phạm vi phần mềm.
- Tự tạo thêm tài liệu/issue nếu không có gap thật giữa yêu cầu, plan, security gate hoặc GitHub Issues.
- Biến tài liệu gửi sếp thành backlog kỹ thuật quá dài.
- Claim hoàn thành khi chưa chạy verification.

Agent bắt buộc:

- Xác định data class trước khi sửa code.
- Dùng `.env.example` với placeholder.
- Viết test cho permission/object-level auth nếu đụng dữ liệu học sinh/sự kiện.
- Mask log.
- Ghi audit cho hành động nhạy cảm.
- Validate payload từ ANSVIS.
- Dùng idempotency cho event.
- Cập nhật docs nếu đổi API/schema/env/deploy/security behavior.
- Kiểm tra `agent-scope-control-rules.md` trước khi bổ sung planning, task hoặc GitHub Issues.
- Cập nhật traceability nếu thay đổi yêu cầu hoặc issue làm lệch giữa docs, plan và GitHub.

## Quy tắc tách workstream khi code

Agent phải tách rõ 3 luồng:

| Luồng | Được làm gì | Không được trộn với |
|---|---|---|
| Product Platform | Backend, database, Web Portal, Mobile App, auth, report, notification | Không chờ train AI; dùng mock/sanitized ANSVIS event |
| ANSVIS Integration | Adapter, payload contract, camera/task registry, event ingestion, dashboard health | Không chứa business rule dài hoặc model training logic |
| AI Model/Pipeline | Facial Recognition config, Littering/Smoking/Student Uniform/Kitchen PPE pipeline, training nếu cần | Không nhét vào Web/App issue |

Nếu issue thuộc Web/Mobile/Backend, chỉ dùng event contract/mock data. Không được kéo thêm việc label dataset, train model hoặc đánh giá mAP vào cùng issue.

Nếu issue thuộc AI custom pipeline, chỉ xử lý pipeline/model/config/metric/shadow mode. Không sửa UI/Web/Mobile trừ khi issue yêu cầu rõ.

## Quy tắc kiểm soát scope/planning

Khi làm việc với plan/task/issues, Agent phải giữ quy trình:

```text
Yêu cầu khách hàng
  -> project docs
  -> implementation planning
  -> GitHub issue
  -> acceptance/gate
```

Không thêm issue mới nếu:

- Issue hiện có đã bao phủ nội dung.
- Nội dung chỉ là ý tưởng phụ chưa được yêu cầu.
- Nội dung thuộc phần cứng/lắp đặt ngoài scope.
- Nội dung chỉ làm bản gửi sếp dài hơn mà không tăng khả năng triển khai.

Chỉ thêm issue mới nếu:

- Có yêu cầu trong docs nhưng chưa có issue.
- Có security/privacy/database gate chưa có issue.
- Có rủi ro Critical/High chưa có issue.
- Có UAT/go-live requirement chưa có issue.
- Một issue quá lớn cần tách khi chuẩn bị triển khai.

Nếu số lượng issue lớn, Agent không được xóa bừa. Phải dùng:

- milestone;
- label;
- GitHub Project view;
- executive summary gọn;
- traceability audit.

Khi user hỏi "có đủ chưa" hoặc "có lan man không", Agent phải kiểm tra bằng evidence từ docs/issues, không trả lời cảm tính.

## Quy trình suy nghĩ trước khi code

Mỗi task phải đi theo thứ tự:

1. Hiểu yêu cầu: task này giải quyết vấn đề gì?
2. Xác định phạm vi: service/module/file nào bị ảnh hưởng?
3. Xác định dữ liệu: có PII, biometric, secret, event, report hay không?
4. Xác định quyền: role nào được phép làm/xem/sửa/xóa?
5. Xác định rủi ro: có thể rò rỉ dữ liệu, gửi nhầm người, ghi trùng event, mất audit không?
6. Đọc pattern hiện có.
7. Chọn thay đổi nhỏ nhất đủ giải quyết vấn đề.
8. Viết/cập nhật test.
9. Implement.
10. Verify.
11. Update docs/runbook.

Nếu không trả lời được bước 3 hoặc 4 thì không nên code tiếp.

## Checklist trước khi sửa file

| Câu hỏi | Nếu có |
|---|---|
| Có chạm dữ liệu học sinh/phụ huynh không? | Cần object-level auth test |
| Có chạm khuôn mặt/biometric không? | Cần consent check, audit, retention |
| Có chạm `.env`/secret không? | Chỉ sửa `.env.example`, không đọc secret thật |
| Có chạm ANSVIS event không? | Cần contract test và idempotency |
| Có đổi database không? | Cần migration |
| Có đổi API không? | Cần OpenAPI/schema và client impact |
| Có đổi notification không? | Cần test đúng người nhận |
| Có đổi report/export không? | Cần audit và permission test |
| Có đổi deploy/ops không? | Cần runbook/rollback |

## Kiến trúc code bắt buộc

Backend service dùng Clean/Hexagonal Architecture:

```text
api -> application -> domain <- infrastructure
```

Ý nghĩa:

- `api`: route, auth guard, dependency, request validation.
- `application`: use case, transaction, orchestration.
- `domain`: entity, policy, business rule, domain error.
- `infrastructure`: database, queue, storage, HTTP client, ANSVIS adapter.
- `schemas`: DTO request/response/event.

Không được để:

- Business rule dài trong route.
- SQL/query rải rác trong API layer.
- ANSVIS raw payload lan sang nhiều service.
- Permission logic duplicate ở nhiều endpoint.
- Domain import framework/database/vendor client.

## Design patterns áp dụng

| Pattern | Dùng khi | Lý do |
|---|---|---|
| Repository | Truy cập database | Dễ test, dễ thay đổi query |
| Application Service | Use case nghiệp vụ | Tập trung flow và transaction |
| Adapter | Tích hợp ANSVIS/S3/push/email | Cô lập vendor |
| Policy | RBAC/ABAC/consent | Không duplicate permission |
| DTO/Schema | API/event contract | Validate, versioning |
| Outbox | Ghi DB rồi phát event | Tránh mất event |
| Idempotency | ANSVIS event/notification | Chống xử lý trùng |
| Strategy | Notification/event mapping | Dễ mở rộng |
| CQRS nhẹ | Report/dashboard | Giảm tải transaction DB |
| Feature Flag | Shadow mode/rollout | Bật/tắt an toàn |

Không dùng pattern để làm code rối hơn. Nếu pattern không giúp đọc rõ hơn hoặc test dễ hơn, không dùng.

## Quy tắc database

Database chính: PostgreSQL.

Trước khi code database, migration, repository, model hoặc query, bắt buộc đọc `implementation-planning/planning/database-and-encryption-plan.md`.

MongoDB không dùng làm primary database cho dữ liệu nghiệp vụ chính vì dữ liệu trường học cần quan hệ, transaction, audit và báo cáo chặt.

Quy tắc:

- Mọi schema change phải có migration.
- Không sửa production DB bằng tay.
- Không lưu media binary trong table.
- Không query bằng string nối input.
- Không service nào đọc schema của service khác.
- JSONB chỉ dùng cho payload linh hoạt đã kiểm soát, không thay thế modeling nghiệp vụ lõi.
- Event table lớn phải tính retention/partitioning.

Security gate trước khi tạo/sửa bảng:

- Xác định bảng/field chứa PII, biometric, evidence, secret hay event nhạy cảm.
- Xác định field nào cần application-level encryption hoặc lookup hash.
- Xác định audit event cho hành động xem/sửa/xóa/export.
- Xác định retention/delete/anonymize policy.
- Xác định test permission/object-level authorization.
- Xác định backup/restore impact nếu migration thay đổi dữ liệu quan trọng.

## Quy tắc ANSVIS/AI

ANSVIS/AIBOX là nguồn event AI, không phải database nghiệp vụ.

Luồng chuẩn:

```text
ANSVIS HTTP Trigger
  -> API Gateway
  -> ANSVIS Adapter
  -> Validate/Auth/Normalize
  -> Event Ingestion
  -> Queue/Outbox
  -> Business Services
```

Quy tắc:

- Validate source/token/HMAC nếu có.
- Validate schema version và payload size.
- Không log raw payload có ảnh/base64/face data.
- Dùng custom payload tối thiểu.
- Dùng signed URL thay vì base64 nếu có media.
- Tắt debug mode production.
- Idempotency key cho mỗi event.
- Chỉ append video cho event cần evidence.
- Model/threshold/ROI/task config phải version hóa.

AI training:

- Điểm danh học sinh và chấm công giáo viên ưu tiên dùng Face Detection/Facial Recognition có sẵn trong ANSVIS.
- Xả rác, hút thuốc, đồng phục học sinh và PPE/bảo hộ bếp phải được coi là custom pipeline/model-rule combination nếu chưa chứng minh model có sẵn đáp ứng đủ.
- Nguồn dữ liệu training/fine-tune/kiểm định AI chỉ lấy từ camera dự án thông qua ANSVIS/AIBOX, trừ khi có phê duyệt riêng bằng văn bản.
- Dataset không nằm trong Git.
- Dataset phải có manifest.
- Dùng mã định danh giả, không dùng tên học sinh.
- Không dùng dataset ngoài/Internet/trường khác để train, benchmark hoặc demo nếu chưa có phê duyệt, consent và kiểm soát bảo mật riêng.
- Model có version, checksum, dataset hash, metric.
- Production model phải qua shadow mode.
- Event nhạy cảm hoặc confidence thấp cần human review.

## Quy tắc consent và privacy

Nếu dùng dữ liệu sinh trắc học:

- Có consent mới được xử lý.
- Consent thiếu thì block mặc định.
- Consent thay đổi phải audit.
- Khi rút consent, cần có quy trình disable/xóa/anonymize theo chính sách.

Phụ huynh:

- Chỉ xem dữ liệu con mình.
- Không xem lớp/trẻ khác.
- Không export dữ liệu nhạy cảm nếu không có quyền.

Giáo viên:

- Chỉ xem lớp/học sinh được phân công.

BGH/Admin:

- Có quyền rộng hơn nhưng vẫn cần audit khi xem/export/sửa dữ liệu nhạy cảm.

## Quy tắc API

Mỗi endpoint phải có:

- Auth requirement.
- Permission policy.
- Request schema.
- Response schema.
- Error code.
- Audit behavior nếu nhạy cảm.
- Test allowed/denied.

Response lỗi:

```json
{
  "error_code": "STABLE_ERROR_CODE",
  "message": "Thông báo dễ hiểu",
  "request_id": "req_..."
}
```

Không trả:

- stack trace;
- password hash;
- token hash;
- secret reference;
- internal exception;
- dữ liệu ngoài quyền user.

## Quy tắc Web/Mobile

- Không gọi API rải rác trong component.
- Dùng feature-based structure.
- Route/screen guard theo role.
- Backend vẫn là nơi enforce quyền cuối cùng.
- Mobile token phải lưu trong secure storage.
- Không lưu dữ liệu nhạy cảm trong localStorage/plain AsyncStorage nếu tránh được.
- Không render HTML không kiểm soát.
- Không show image/video evidence nếu user không có quyền.

Feature structure:

```text
features/
  attendance/
    api/
    components/
    hooks/
    screens-or-pages/
    types.ts
```

## Quy tắc log

Log đúng:

```json
{
  "level": "info",
  "service": "ansvis-adapter-service",
  "request_id": "req_xxx",
  "event_id": "evt_xxx",
  "camera_id": "cam_gate_01",
  "message": "ansvis_event_ingested"
}
```

Log sai:

```json
{
  "student_name": "Real Student",
  "image_base64": "...",
  "token": "...",
  "rtsp_url": "<redacted-credentialed-rtsp-url>"
}
```

Metric cần có khi triển khai:

- API latency/error rate.
- Event ingestion rate.
- Queue depth/DLQ.
- ANSVIS task status/process time.
- Storage usage.
- Login fail spike.
- Export spike.
- Worker retry/failure.

## Quy tắc test

| Thay đổi | Test tối thiểu |
|---|---|
| Auth/permission | Allowed + denied role tests |
| Dữ liệu học sinh | Object-level authorization tests |
| Consent/biometric | Consent allow/block tests |
| ANSVIS payload | Contract tests bằng payload đã sanitize |
| Event ingestion | Idempotency, invalid payload, retry |
| Notification | Đúng người nhận, không gửi media nhạy cảm |
| Report/export | Permission + audit |
| Database | Migration apply |
| Logging | Không lộ secret/PII trong log |

Test fixture phải dùng dữ liệu giả.

## Quy tắc verification

Trước khi báo xong, agent phải nói rõ đã chạy gì.

Tùy loại task:

- Docs: kiểm link, marker rỗng, mục bắt buộc.
- Backend: test, lint, migration.
- Frontend/mobile: lint, typecheck, test/build nếu có.
- Security: secret scan, permission tests.
- AI integration: contract test, idempotency test.

Nếu chưa chạy được, phải nói rõ lý do và rủi ro.

## Quy tắc maintainability

- Code/API dùng tiếng Anh.
- Tài liệu khách hàng có thể dùng tiếng Việt.
- Mỗi service có README.
- Function ngắn, tên rõ.
- File quá dài phải tách.
- Không copy-paste business rule.
- Không tạo service mới nếu chỉ để chứa vài hàm phụ.
- Không tạo nhiều docs nhỏ nếu một docs tổng hợp dễ đọc hơn.
- Mọi decision lớn nên có ADR trong `docs/decisions/`.

## Khi nào phải hỏi lại user

Hỏi lại nếu:

- Cần chọn kiến trúc khác plan.
- Cần dùng secret/credential thật.
- Cần dữ liệu học sinh/ảnh mặt thật.
- Cần xóa dữ liệu.
- Cần production access.
- Requirement mâu thuẫn với security/privacy.
- Có lựa chọn ảnh hưởng nghiệm thu hoặc chi phí lớn.

Nếu có thể tiếp tục an toàn bằng assumption nhỏ, ghi rõ assumption và tiếp tục.
