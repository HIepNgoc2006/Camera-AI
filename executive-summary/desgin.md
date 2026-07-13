# KẾ HOẠCH PHÁT TRIỂN HỆ THỐNG AI CAMERA TRƯỜNG HỌC

## 1. Mục tiêu tài liệu

Mục tiêu hiện tại chưa phải là triển khai ngay, mà là chốt rõ:

- Hệ thống sẽ làm những nhóm việc nào.
- Phạm vi phần mềm gồm những gì.
- Những hạng mục bảo mật/dữ liệu cần kiểm soát trước khi dùng dữ liệu thật.
- Các nhóm task đã được đưa lên GitHub Issues để theo dõi.
- Những điểm cần xác nhận trước khi chuyển sang giai đoạn code.

## 2. Tóm tắt điều hành

Hệ thống AI Camera trường học là hệ thống phần mềm có mức nhạy cảm cao vì có thể xử lý dữ liệu học sinh, phụ huynh, giáo viên, khuôn mặt, điểm danh, chấm công, ảnh/video sự kiện và dữ liệu vi phạm.

Vì vậy kế hoạch phát triển được thiết kế theo hướng:

- **Security-first**: bảo mật, phân quyền, consent, audit, mã hóa dữ liệu được đưa vào ngay từ đầu.
- **Triển khai tuần tự**: hiện giả định một developer chính thực hiện, không lập kế hoạch theo kiểu nhiều team chạy song song.
- **Không mở rộng sang phần cứng**: phạm vi chỉ gồm phần mềm, backend, AI integration, Web, Mobile, database, bảo mật, monitoring và vận hành.
- **Có traceability**: yêu cầu khách hàng → tài liệu → plan → GitHub Issues → acceptance/gate.

Hiện tại đã hoàn thành vòng chuẩn bị planning/docs/issues. Chưa bắt đầu codebase sản phẩm.

## 3. Phạm vi dự án

### 3.1 Trong phạm vi phần mềm

| Nhóm | Nội dung |
|---|---|
| Backend/API | API Gateway, auth, phân quyền, nghiệp vụ điểm danh/chấm công/vi phạm/báo cáo |
| AI/ANSVIS integration | Nhận event từ ANSVIS/AIBOX, validate, normalize, chống trùng, shadow mode |
| Web Portal | Dashboard cho BGH/Admin/Giáo viên/Phụ huynh theo quyền |
| Mobile App | React Native App cho phụ huynh/giáo viên/BGH theo quyền |
| Database | PostgreSQL, schema, migration, audit, retention, backup |
| Security/Privacy | Consent, RBAC/ABAC, object-level authorization, encryption, secret management |
| QA/UAT | Test chức năng, test bảo mật, test tích hợp, UAT, production readiness |
| Operations | Monitoring, logging, backup/restore, incident response, release/rollback |

### 3.2 Ngoài phạm vi phần mềm

| Ngoài phạm vi | Ghi chú |
|---|---|
| Mua camera/phần cứng | Do khách hàng hoặc đơn vị thi công phụ trách |
| Lắp đặt camera | Không thuộc scope phần mềm |
| Đi dây mạng/vật lý | Không thuộc scope phần mềm |
| Khảo sát hiện trường phần cứng | Chỉ thực hiện nếu có phụ lục/thỏa thuận riêng |
| Bảo trì phần cứng camera | Không thuộc scope phần mềm |

Điều kiện tích hợp: bên phụ trách phần cứng/hạ tầng bàn giao RTSP/ONVIF, ANSVIS/AIBOX, API hoặc thông tin kết nối cần thiết.

## 4. Các nhóm chức năng chính

| Nhóm chức năng | Mục tiêu |
|---|---|
| Điểm danh học sinh | Ghi nhận ra/vào, trạng thái điểm danh, đi trễ, đối soát theo quyền |
| Chấm công cán bộ/giáo viên | Ghi nhận vào/ra, hỗ trợ báo cáo công |
| Phát hiện vi phạm | Đồng phục, đi trễ, xả rác, hút thuốc, thiếu bảo hộ bếp |
| Happiness index | Chỉ triển khai nếu phạm vi/privacy được duyệt; ưu tiên dạng tổng hợp/ẩn danh |
| Thông báo | Gửi đúng người, không lộ dữ liệu nhạy cảm trong push notification |
| Dashboard/report | Thống kê, lọc theo vai trò, export có audit |
| Quản trị hệ thống | User, role, permission, camera mapping, ANSVIS status |
| Consent/privacy | Quản lý đồng ý xử lý dữ liệu sinh trắc học và rút consent |
| Audit/security | Ghi nhận thao tác nhạy cảm, phát hiện rủi ro, hỗ trợ điều tra sự cố |

## 5. Kiến trúc triển khai dự kiến

```text
Camera RTSP/ONVIF
  -> ANSVIS/AIBOX AI Task
  -> HTTP Trigger/Event Log
  -> API Gateway
  -> ANSVIS Adapter
  -> Event Ingestion + Queue/Outbox
  -> Attendance / Timekeeping / Violation / Notification / Report
  -> PostgreSQL / Object Storage / Audit / Monitoring
  -> Web Portal / Mobile App
```

Định hướng kỹ thuật:

| Thành phần | Lựa chọn |
|---|---|
| Backend | Python/FastAPI hoặc stack tương đương, microservices-ready |
| Web Portal | Web app theo module/feature |
| Mobile App | React Native dùng chung codebase iOS/Android |
| Database chính | PostgreSQL |
| Cache/rate limit/lock | Redis |
| Queue/event processing | RabbitMQ hoặc queue tương đương |
| Media/evidence storage | Private object storage như MinIO/S3-compatible |
| AI/video analytics | ANSVIS/AIBOX theo tài liệu ANSCENTER |
| Security scan | Secret scan, dependency scan, container scan, OWASP/ZAP baseline |

## 6. Bảo mật và dữ liệu

Bảo mật là phần bắt buộc xuyên suốt, không phải bước bổ sung cuối.

Các nguyên tắc chính:

- Không dùng dữ liệu thật khi chưa có consent và chính sách dữ liệu rõ.
- Không lưu ảnh/video binary trong PostgreSQL.
- Evidence ảnh/video lưu ở private object storage, truy cập bằng signed URL ngắn hạn.
- PostgreSQL là database nghiệp vụ chính.
- Dữ liệu nhạy cảm cần phân loại theo bảng/field trước khi code.
- Dữ liệu sinh trắc học chỉ xử lý khi có consent hợp lệ.
- Mọi thao tác xem/sửa/xóa/export dữ liệu nhạy cảm phải có audit log.
- Production secret/key không nằm trong Git hoặc source code.
- Backup phải mã hóa và phải restore test được.

Các hạng mục bảo mật đã được đưa thành task riêng:

| Hạng mục | Mục tiêu |
|---|---|
| RBAC/ABAC | Phụ huynh chỉ xem con mình, giáo viên chỉ xem lớp được phân công |
| Consent | Chặn xử lý biometric nếu thiếu consent |
| Audit log | Ghi lại thao tác nhạy cảm |
| Database encryption | Mã hóa dữ liệu nhạy cảm, key rotation, backup encryption |
| Evidence policy | Private storage, signed URL TTL, access audit |
| DDoS/API abuse | Rate limit, webhook hardening, monitoring |
| Incident response | Quy trình phát hiện, cô lập, xử lý, thông báo và postmortem |

## 7. Kế hoạch triển khai theo milestone

| Milestone | Nội dung chính | Gate để chuyển tiếp |
|---|---|---|
| M1 - Docs Baseline | Chốt tài liệu, yêu cầu, GitHub workflow, traceability | Yêu cầu và scope rõ, không lệch phần cứng |
| M2 - Codebase Foundation | Monorepo, Docker, `.env.example`, CI, secret scan | Không có secret thật, môi trường local chạy được |
| M3 - Backend Core | Auth, user, school, consent, audit, database core | RBAC/ABAC, consent, audit, migration baseline |
| M4 - AI/ANSVIS Integration | HTTP Trigger, ANSVIS Adapter, event ingestion, AI task mapping | Validate payload, idempotency, không log media nhạy cảm |
| M5 - Web Portal | Dashboard, admin, teacher/parent view, report, consent | Route guard, permission UI, không lộ dữ liệu |
| M6 - Mobile App | React Native app, auth, attendance, notification, consent | Secure token storage, permission guard |
| M7 - Integration & QA | E2E, contract test, performance, 34-camera benchmark | Flow chính pass, không còn blocker/critical |
| M8 - Security Hardening | Scan, backup/restore, incident drill, production readiness | Không còn Critical/High security chưa xử lý |
| M9 - UAT & Go-live | UAT, đào tạo, bàn giao, hyper-care | Khách hàng xác nhận nghiệm thu theo module |

## 8. Trạng thái planning và issue tracking

Hiện GitHub Issues đã được chuẩn hóa để theo dõi dự án. Tổng số issue hiện tại: **97 issue mở**.

| Nhóm issue | Số lượng | Mục đích |
|---|---:|---|
| Foundation ban đầu | 28 | Docs, GitHub workflow, codebase foundation, skeleton, QA/runbook |
| Risk/operations/security bổ sung | 18 | DDoS, NTP, ANSVIS capacity, signed URL, consent withdrawal, backup, queue, model drift |
| DBSEC | 12 | PostgreSQL, ERD, data classification, encryption, key rotation, audit, retention, hardening |
| Module chi tiết | 31 | Backend services, Web screens, Mobile screens, UAT, production readiness |
| Traceability gap | 8 | 34-camera mapping, happiness index, per-violation metrics, parent/teacher Web, benchmark, deployment/capacity |

Lưu ý: 97 issue là backlog kỹ thuật để không bỏ sót việc. Khi báo cáo cho sếp, chỉ nên xem Executive Overview theo Critical/High/Blocked, không cần đọc toàn bộ issue.

## 9. Các điểm cần xác nhận trước khi code

| Điểm cần xác nhận | Lý do |
|---|---|
| Happiness index có triển khai không, và chỉ ở mức tổng hợp/ẩn danh hay sâu hơn | Đây là hạng mục nhạy cảm privacy, không nên làm nếu chưa rõ mục đích |
| Quy trình consent phụ huynh | Bắt buộc trước khi xử lý dữ liệu sinh trắc học |
| Mapping 34 camera | Cần xác nhận camera nào phục vụ task nào, khu vực nào, event nào |
| ANSVIS license/GPU/task limit | Ảnh hưởng khả năng xử lý 34 camera |
| Web Portal có cho phụ huynh không hay chỉ mobile cho phụ huynh | Docs hiện có đề cập phụ huynh trên Web Portal, cần chốt phạm vi |
| Chính sách lưu evidence | Ảnh/video giữ bao lâu, ai được xem/export |
| Cơ chế vận hành sau bàn giao | Ai theo dõi lỗi, backup, cảnh báo, support |
| Tiêu chí nghiệm thu AI | Cần thống nhất cách đo false positive/false negative/human review |

## 10. Rủi ro chính và cách kiểm soát

| Rủi ro | Mức | Kiểm soát |
|---|---:|---|
| Rò rỉ dữ liệu học sinh/khuôn mặt | Rất cao | Consent, encryption, private storage, audit, log masking |
| Phụ huynh xem nhầm dữ liệu trẻ khác | Rất cao | Object-level authorization, permission test |
| Notification gửi sai người | Rất cao | Recipient permission check, delivery audit |
| AI nhận diện sai/gắn nhãn sai | Cao | Shadow mode, human review, appeal/correction workflow |
| ANSVIS/GPU/license không đủ tải 34 camera | Cao | Verify license, benchmark, capacity baseline |
| Backup không restore được | Cao | Encrypted backup, restore drill |
| DDoS/API abuse/webhook flood | Cao | Rate limit, WAF/CDN nếu có, webhook auth, body size limit |
| Một developer là điểm nghẽn | Cao | Làm tuần tự, giới hạn WIP, ghi docs/runbook liên tục |
| Planning/issue quá nhiều gây rối | Trung bình | Dùng Executive View, milestone, label, không thêm issue nếu không có gap thật |

## 11. Go/no-go trước khi bắt đầu code

Chỉ nên bắt đầu code khi các điều kiện sau được xác nhận:

| Điều kiện | Trạng thái mong muốn |
|---|---|
| Scope phần mềm đã chốt | Không thêm task phần cứng/lắp đặt |
| Critical/High issues đã được review | Không có issue mơ hồ hoặc thiếu acceptance |
| Security gate đã rõ | Consent, RBAC, audit, encryption, backup, incident response |
| Architecture baseline đã rõ | PostgreSQL, object storage, queue, ANSVIS Adapter, API Gateway |
| Traceability đã khớp | Yêu cầu → docs → plan → issue |
| Thứ tự triển khai đã rõ | Làm tuần tự theo milestone, không chạy song song quá nhiều |

## 12. Đề xuất bước tiếp theo

Đề xuất chưa code ngay. Bước tiếp theo nên là:

1. Sếp/PM review bản kế hoạch này.
2. Chốt các điểm cần xác nhận ở Mục 9.
3. Review nhóm issue Critical/High trên GitHub.
4. Sau khi thống nhất, bắt đầu từ milestone M2 - Codebase Foundation:
   - monorepo structure;
   - `.gitignore` và `.env.example`;
   - Docker Compose local stack;
   - secret scan;
   - lint/test baseline.

Kết luận: kế hoạch hiện đã đủ để chuyển sang giai đoạn chuẩn bị codebase sau khi được xác nhận. Việc giữ backlog kỹ thuật chi tiết là cần thiết để kiểm soát rủi ro, nhưng khi báo cáo quản lý chỉ nên dùng bản tổng hợp này và GitHub Executive View.\n