# Agent scope control rules

## Mục tiêu

File này dùng để ngăn Agent làm việc lan man khi dự án đang ở giai đoạn thiết kế, planning, task và GitHub Issues.

Nguyên tắc chính: **không mở rộng tài liệu, task hoặc issue chỉ vì có thể nghĩ thêm được việc mới. Chỉ bổ sung khi có gap thật giữa yêu cầu, plan, security gate hoặc khả năng triển khai.**

## Current mission lock

Nhiệm vụ hiện tại của dự án được khóa ở phạm vi:

1. **Xây dựng/hoàn thiện các model hoặc pipeline còn thiếu**:
   - Littering Detection.
   - Smoking Detection.
   - Student Uniform Detection.
   - Kitchen PPE Detection.
   - Facial Recognition chỉ cấu hình/tích hợp theo ANSVIS nếu model có sẵn đáp ứng, không coi là model cần xây từ đầu.
2. **Phát triển hệ thống phần mềm để sử dụng, theo dõi và quản lý các event AI**:
   - Backend/API.
   - ANSVIS Adapter/Event Ingestion.
   - Web Portal.
   - Mobile App.
   - Database, audit, evidence storage, notification, report.
3. **Đảm bảo quy trình triển khai đúng và an toàn**:
   - mock/sanitized event trước;
   - baseline/shadow mode trước production;
   - human review với event nhạy cảm;
   - security/privacy/consent/audit xuyên suốt.

Ngoài phạm vi hiện tại:

- Không mở rộng sang mua/lắp/căn chỉnh camera.
- Không mở rộng sang khảo sát hiện trường, đi dây, mạng vật lý.
- Không tự thêm module AI mới ngoài 6 chức năng đã chốt.
- Không biến ANSTS/training thành điều kiện chặn Web/App/Backend.
- Không thêm dataset thật, face image, video camera hoặc credential vào repo/issue/docs.

Khi có yêu cầu mới, Agent phải kiểm tra nó có phục vụ trực tiếp 2 mục tiêu chính không: **model/pipeline còn thiếu** hoặc **app/web/backend để quản lý event AI**. Nếu không, phải ghi là ngoài scope hoặc cần xác nhận riêng.

## Quy tắc phân tầng tài liệu

Agent phải phân biệt rõ 3 tầng:

| Tầng | Đối tượng đọc | Mục tiêu | Không được làm |
|---|---|---|---|
| Executive summary | Sếp/khách hàng/quản lý | Ngắn, rõ, theo nhóm việc, rủi ro, trạng thái | Không nhồi toàn bộ issue kỹ thuật |
| Project docs | Khách hàng + kỹ thuật | Mô tả yêu cầu, flow, kiến trúc, nghiệm thu | Không biến thành backlog chi tiết |
| Implementation planning | Dev/Agent/PM kỹ thuật | Task, rule, security gate, issue tracking | Không dùng làm bản trình bày trực tiếp cho sếp nếu quá dài |

Nếu cần viết cho sếp, ưu tiên tạo/cập nhật file trong `executive-summary`.
Nếu cần hướng dẫn dev/agent, cập nhật `implementation-planning`.
Nếu cần mô tả yêu cầu khách hàng, cập nhật `project-docs`.

## Quy tắc trước khi thêm tài liệu mới

Trước khi tạo file mới, Agent phải kiểm tra:

1. File hiện có có thể chứa nội dung này không?
2. Nội dung có phải là quyết định/gate/traceability độc lập không?
3. Nếu thêm file mới, người đọc có dễ tìm thấy qua index không?
4. File mới có làm trùng lặp nội dung đã có không?

Chỉ tạo file mới khi ít nhất một điều kiện đúng:

- Nội dung là một nguồn chuẩn riêng, ví dụ database/encryption.
- Nội dung là audit/checkpoint riêng, ví dụ pre-code readiness.
- Nội dung phục vụ nhóm độc giả khác rõ ràng, ví dụ bản gửi sếp.
- Nội dung nếu gộp vào file cũ sẽ làm file đó khó đọc hoặc khó bảo trì.

Nếu tạo file mới, bắt buộc cập nhật index liên quan.

## Quy tắc trước khi thêm GitHub Issue

Không thêm issue mới nếu chỉ là ý tưởng phụ.

Chỉ thêm issue khi issue đó thỏa ít nhất một điều kiện:

- Có yêu cầu trong customer docs nhưng chưa có issue theo dõi.
- Có security/privacy/database gate chưa được theo dõi.
- Có rủi ro Critical/High chưa có issue giảm thiểu.
- Có milestone/go-live/UAT requirement chưa có issue.
- Có traceability gap giữa docs, plan và issue.
- Một issue hiện tại quá lớn và cần tách để có thể hoàn thành trong 1-3 ngày khi triển khai.

Trước khi thêm issue, Agent phải kiểm tra trùng bằng title hoặc nội dung tương đương.

Mỗi issue mới phải có:

- Prefix rõ: `[DOCS]`, `[OPS]`, `[BE]`, `[AI]`, `[WEB]`, `[MOB]`, `[SEC]`, `[QA]`, `[DBSEC]`.
- Milestone.
- Labels type/area/priority.
- Acceptance criteria.
- Security/privacy impact nếu liên quan dữ liệu nhạy cảm.
- Không chứa secret, dữ liệu thật, ảnh/video thật, RTSP credential hoặc thông tin học sinh thật.

## Quy tắc chống phình scope

Agent không được:

- Tự thêm module mới ngoài yêu cầu khách hàng.
- Tự thêm task phần cứng, khảo sát, lắp camera, đi dây mạng.
- Tự đổi kiến trúc lớn khi chưa có yêu cầu.
- Tự biến planning thành timeline chi tiết nếu user đã nói ngày giờ đàm phán sau.
- Tự thêm nhiều file nhỏ khi một file tổng hợp là đủ.
- Tự tạo quá nhiều issue nếu chỉ cần ghi vào một issue hiện có.
- Tự xem mọi rủi ro giả định là task bắt buộc.

Agent phải:

- Giữ scope phần mềm.
- Bám theo traceability: yêu cầu -> docs -> plan -> issue.
- Ưu tiên cập nhật file hiện có.
- Ghi rõ nếu một điểm là assumption.
- Ghi rõ nếu một điểm cần sếp/khách hàng xác nhận.

## Quy tắc traceability

Khi thay đổi yêu cầu, plan hoặc issue, Agent phải kiểm tra file:

```text
implementation-planning/planning/requirements-issues-traceability-audit.md
```

Nếu thay đổi làm mất đồng bộ giữa docs và issues, Agent phải cập nhật traceability hoặc tạo issue `[DOCS] Maintain requirements-to-issues traceability matrix`.

Traceability tối thiểu:

```text
Customer requirement
  -> project-docs
  -> implementation-planning
  -> GitHub issue
  -> acceptance / gate
```

## Quy tắc khi user hỏi "có đủ chưa?"

Agent không được trả lời cảm tính.

Phải kiểm tra:

- Files planning chính.
- Customer docs.
- GitHub issue list.
- Security/privacy gate.
- QA/UAT/acceptance gate.
- Known gaps trong traceability audit.

Sau đó trả lời theo 3 mức:

| Mức | Ý nghĩa |
|---|---|
| Đạt | Có docs + plan + issue + acceptance rõ |
| Đạt cơ bản | Có coverage nhưng cần tách nhỏ hoặc review thêm khi code |
| Chưa đạt | Có yêu cầu/gate nhưng thiếu docs, plan hoặc issue |

## Quy tắc khi user hỏi "có bị lan man không?"

Agent phải đánh giá theo 2 chiều:

1. Nội dung có lệch khỏi scope không?
2. Cách tracking có quá dày so với người đọc không?

Nếu nội dung đúng nhưng tracking quá dày, không được xóa bừa. Phải đề xuất:

- Executive view gọn cho sếp.
- Technical backlog giữ chi tiết cho dev.
- GitHub Project filter theo Critical/High/Blocked.
- Không thêm issue mới nếu không có gap thật.

## Quy tắc dừng bổ sung planning

Khi đã có đủ:

- Customer docs.
- System master plan.
- Architecture/stack.
- Tooling requirements.
- Security/privacy.
- Database/encryption.
- AI/ANSVIS.
- QA/acceptance.
- Operations/tracking.
- Risk assessment.
- Agent rules.
- Traceability audit.
- GitHub Issues theo milestone.

Agent phải dừng việc tự mở rộng planning, trừ khi:

- User yêu cầu rõ.
- Có gap thật được phát hiện.
- Có yêu cầu mới từ khách hàng/sếp.
- Có rủi ro Critical/High chưa được ghi nhận.

## Quy tắc trước khi chuyển sang code

Không bắt đầu code chỉ vì planning đã nhiều.

Trước khi code cần kiểm tra:

- User đã xác nhận chuyển sang code.
- Issue hoặc milestone code cụ thể đã được chọn.
- Scope issue đủ nhỏ.
- Security/privacy impact đã rõ.
- Test/verification đã rõ.
- Không cần secret/dữ liệu thật/production access.

Nếu chưa có issue cụ thể, Agent phải hỏi hoặc đề xuất issue bắt đầu, không tự chọn module lớn.
