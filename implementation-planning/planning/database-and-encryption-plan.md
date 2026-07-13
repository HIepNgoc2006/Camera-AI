# Database and encryption plan

## Mục tiêu

File này là tài liệu chuẩn cho mọi quyết định liên quan đến PostgreSQL, lưu trữ dữ liệu, mã hóa, backup, retention và kiểm soát rò rỉ dữ liệu của hệ thống AI Camera trường học.

Hệ thống có thể xử lý dữ liệu trẻ em, phụ huynh, giáo viên, điểm danh, chấm công, ảnh/video sự kiện, dữ liệu khuôn mặt và dữ liệu vi phạm. Vì vậy database không chỉ cần đúng nghiệp vụ, mà phải có khả năng bảo vệ dữ liệu, audit, khôi phục và bàn giao vận hành.

Nguyên tắc mặc định:

- PostgreSQL là database nghiệp vụ chính.
- Không dùng MongoDB làm database giao dịch chính.
- Không lưu binary ảnh/video trong PostgreSQL.
- Object storage phải private và chỉ truy cập qua signed URL ngắn hạn.
- Secret, credential, key mã hóa không nằm trong Git hoặc database business.
- Dữ liệu sinh trắc học chỉ xử lý khi có consent hợp lệ.
- Mọi truy cập/xuất/sửa/xóa dữ liệu nhạy cảm phải có audit log.

## Kiến trúc lưu trữ dữ liệu

```text
Web / Mobile / ANSVIS HTTP Trigger
            |
        API Gateway
            |
 Backend Services / Workers
            |
 PostgreSQL  <->  Redis/RabbitMQ  <->  Object Storage
            |
 Audit / Backup / Monitoring / Secret Manager
```

| Thành phần | Vai trò | Quy tắc bảo mật |
|---|---|---|
| PostgreSQL | Lưu dữ liệu nghiệp vụ, quan hệ, trạng thái xử lý, audit metadata | TLS nếu triển khai production, backup mã hóa, migration bắt buộc |
| Object Storage | Lưu ảnh/video evidence, model artifact, export file tạm | Bucket private, server-side encryption, signed URL ngắn hạn |
| Redis | Cache, rate limit, lock tạm thời | Không lưu dữ liệu sinh trắc học hoặc PII lâu dài |
| RabbitMQ/Queue | Hàng đợi event, retry, DLQ | Không gửi raw image/base64/secret qua queue |
| Secret Manager/KMS | Lưu secret và key mã hóa | Không lưu key trong repo, hỗ trợ rotation |
| Backup Storage | Lưu bản backup database/object storage/config | Mã hóa, giới hạn quyền, restore drill định kỳ |

## PostgreSQL schema plan

Khuyến nghị giai đoạn đầu dùng một PostgreSQL cluster, chia schema theo domain để dễ quản lý và sẵn sàng tách service khi cần.

| Schema | Dữ liệu chính | Ghi chú |
|---|---|---|
| `identity` | user, role, permission, session, MFA, refresh token metadata | Token thật phải hash/mã hóa, không lưu plaintext |
| `school` | student, parent/guardian, teacher/staff, class, assignment | Dữ liệu cá nhân mức Critical |
| `privacy` | consent, consent event, data subject request, purpose, retention policy | Là nguồn kiểm soát biometric processing |
| `camera` | camera metadata, zone, camera status, ANSVIS mapping | Credential thật nằm ở secret manager |
| `integration` | source system, webhook config metadata, contract version | Không lưu webhook secret plaintext |
| `events` | normalized event, raw metadata đã sanitize, idempotency key, processing error | Event table cần index/partition/retention |
| `attendance` | student attendance, late record, review/correction | Có audit khi sửa |
| `timekeeping` | staff check-in/out, shift, correction | Có audit khi sửa |
| `violation` | violation record, review status, manual correction | Evidence chỉ lưu object key |
| `evidence` | evidence metadata, object key, signed URL event, access log | Không lưu binary trong DB |
| `notification` | notification, template, recipient, delivery log, device token metadata | Device token cần mã hóa hoặc token hóa |
| `reporting` | report job, export request, dashboard snapshot/read model | Export phải có audit và TTL |
| `ai_registry` | dataset manifest, model artifact, model version, metric, approval | Không lưu dataset thật trong Git |
| `audit` | audit log, security event, admin action | Append-only logic, không cho sửa/xóa tùy tiện |

## Data classification theo nhóm bảng

| Nhóm dữ liệu | Ví dụ | Mức nhạy cảm | Bắt buộc xử lý |
|---|---|---:|---|
| Biometric | face image, crop, embedding, face DB reference | Critical | Consent, application-level encryption nếu lưu, audit, retention ngắn |
| Student/parent profile | tên, lớp, người giám hộ, liên hệ | Critical | RBAC/ABAC, object-level auth, audit khi export |
| Attendance/timekeeping | check-in/out, đi trễ, chấm công | High | Audit khi sửa, retention, quyền theo vai trò |
| Violation/evidence | ảnh/video vi phạm, review status | High | Private storage, signed URL, export audit |
| ANSVIS event | event metadata, camera, confidence, object key | High | Schema validation, idempotency, masking |
| Notification | nội dung thông báo, recipient, device token | High | Không lộ dữ liệu nhạy cảm trong push, device token bảo vệ |
| Report/export | file báo cáo, snapshot, query result | High | TTL, audit, watermark nếu cần |
| Logs/traces/errors | request log, error detail, metric | Medium/High | Redaction, không PII/secret/biometric |
| Secret/config/license | DB password, S3 key, RTSP credential, ANSVIS token | Critical | Secret manager, rotation, không Git |

Nếu chưa chắc dữ liệu thuộc mức nào, phân loại lên mức cao hơn.

## Quy tắc thiết kế bảng

Mỗi bảng nghiệp vụ cần xác định trước:

- Chủ sở hữu domain/service.
- Dữ liệu nhạy cảm trong bảng.
- Field nào cần audit khi thay đổi.
- Field nào cần mã hóa.
- Field nào cần index.
- Field nào cần retention hoặc anonymize.
- API/role nào được đọc/ghi.
- Migration tạo/sửa bảng.
- Test permission và test migration.

Không tạo bảng chỉ để chứa JSONB tùy tiện. JSONB chỉ dùng cho payload linh hoạt đã kiểm soát, ví dụ metadata ANSVIS đã sanitize hoặc cấu hình có schema version.

## Chiến lược mã hóa

### Encryption in transit

- Public API bắt buộc HTTPS/TLS.
- Backend kết nối PostgreSQL qua TLS ở staging/production nếu hạ tầng hỗ trợ.
- ANSVIS webhook phải có token/HMAC/source validation.
- Internal service dùng private network và service token; có thể nâng lên mTLS khi hạ tầng sẵn sàng.
- Không truyền RTSP credential, S3 secret, database password trong URL/log.

### Encryption at rest

- PostgreSQL dùng disk/volume encryption ở môi trường staging/production.
- Database backup phải được mã hóa trước khi lưu ra backup storage.
- Object storage dùng server-side encryption.
- Export/report file chứa dữ liệu cá nhân phải có TTL và được xóa sau thời hạn.
- Không để public bucket.

### Application-level encryption

Áp dụng cho dữ liệu cực nhạy cảm nếu backend bắt buộc phải lưu:

| Dữ liệu | Cách lưu khuyến nghị |
|---|---|
| Face embedding | Ciphertext + `key_id` + metadata tối thiểu; không log |
| Device token | Mã hóa hoặc token hóa; không hiển thị lại plaintext |
| Credential reference | Lưu reference tới secret manager, không lưu secret thật |
| Export file metadata | Lưu object key + TTL + audit; file thật ở object storage private |
| PII không cần search trực tiếp | Mã hóa application-level |

Với field cần tìm kiếm:

- Không search trực tiếp trên ciphertext.
- Dùng HMAC/hash lookup column cho nhu cầu lookup chính xác.
- Giá trị gốc vẫn được mã hóa.
- HMAC key phải nằm trong secret manager/KMS, không nằm trong database.

Không dùng encryption để thay thế authorization. Dữ liệu đã mã hóa vẫn phải có RBAC/ABAC/object-level authorization.

## Key management

Key và secret phải được quản lý ngoài source code.

| Hạng mục | Quy tắc |
|---|---|
| Master key/KMS key | Lưu trong secret manager/KMS, không lưu trong DB |
| Data encryption key | Dùng envelope encryption, có `key_id` |
| Rotation | Có kế hoạch rotate định kỳ hoặc khi nghi ngờ lộ |
| Revocation | Có quy trình revoke key/secret khi incident |
| Recovery | Có quy trình khôi phục key an toàn, giới hạn người truy cập |
| Audit | Mọi thao tác rotate/revoke/read secret production phải có audit |

Quy tắc code:

- Không hard-code key.
- Không print key ra console/log.
- Không đưa key vào issue, screenshot, tài liệu gửi ngoài.
- Test encryption dùng fake key trong test environment.
- Production key không dùng chung với staging/local.

## Object storage và evidence

PostgreSQL chỉ lưu metadata:

- `object_key`
- `bucket`
- `content_type`
- `size`
- `checksum`
- `created_at`
- `retention_until`
- `linked_event_id`
- `sensitivity`
- `encryption_status`

Không lưu:

- image binary;
- video binary;
- base64 image;
- full public URL dài hạn;
- credential truy cập bucket.

Signed URL:

- TTL ngắn.
- Chỉ tạo sau khi kiểm tra quyền.
- Ghi audit: ai xem, xem evidence nào, thời gian, mục đích nếu cần.
- Không gửi signed URL trực tiếp trong push notification.

## Consent-aware data flow

Với biometric hoặc nhận diện khuôn mặt:

1. Kiểm tra consent trước khi enrollment.
2. Kiểm tra consent trước khi xử lý.
3. Kiểm tra consent trước khi lưu kết quả.
4. Kiểm tra consent trước khi hiển thị/export.
5. Nếu consent bị rút, chuyển trạng thái xử lý sang blocked/disabled.
6. Chạy workflow xóa, ẩn danh hoặc vô hiệu hóa dữ liệu theo policy.
7. Audit mọi thay đổi consent.

Mặc định khi consent thiếu hoặc không rõ: block biometric processing.

## Audit log

Audit log bắt buộc với:

- login/admin login thất bại nhiều lần;
- thay đổi role/permission;
- xem/export dữ liệu học sinh;
- xem/export evidence;
- sửa điểm danh/chấm công/vi phạm;
- thay đổi consent;
- tạo signed URL;
- thay đổi camera mapping/ANSVIS config;
- rotate/revoke secret;
- restore backup;
- xóa/anonymize dữ liệu.

Audit log tối thiểu gồm:

| Field | Ý nghĩa |
|---|---|
| `audit_id` | ID duy nhất |
| `timestamp` | Thời điểm |
| `actor_id` | Người/service thực hiện |
| `actor_role` | Vai trò |
| `action` | Hành động ổn định, ví dụ `EVIDENCE_VIEWED` |
| `resource_type` | Loại tài nguyên |
| `resource_id` | ID tài nguyên |
| `request_id` | Trace request |
| `ip_address` | IP nếu có |
| `user_agent` | Thiết bị/trình duyệt nếu có |
| `result` | success/denied/failed |
| `reason` | Lý do nếu cần |

Không ghi PII/biometric/raw payload đầy đủ vào audit log nếu không cần. Audit log nên tham chiếu resource ID thay vì copy dữ liệu nhạy cảm.

## Retention, delete và anonymize

Mỗi bảng phải có chính sách vòng đời.

| Dữ liệu | Chính sách mặc định |
|---|---|
| Face image/crop | Không lưu nếu không bắt buộc; nếu lưu phải có TTL ngắn |
| Face embedding/reference | Lưu khi có consent; xóa/vô hiệu hóa khi rút consent |
| Attendance/timekeeping | Lưu theo yêu cầu nghiệp vụ/nhà trường, có audit khi sửa |
| Violation evidence | Lưu theo thời hạn được duyệt, tự xóa hoặc archive |
| Notification | Lưu metadata, không giữ nội dung nhạy cảm quá lâu |
| Export/report file | TTL ngắn, tự xóa sau thời hạn |
| ANSVIS raw metadata | Chỉ giữ bản sanitize, có retention |
| Logs | Retention riêng, redaction bắt buộc |
| Backup | Retention riêng, mã hóa, kiểm soát quyền |

Retention job nguy hiểm phải có:

- dry-run mode;
- log số lượng bản ghi dự kiến ảnh hưởng;
- approval nếu xóa dữ liệu quan trọng;
- backup trước khi chạy lần đầu hoặc trước thay đổi lớn;
- audit kết quả.

## Backup và restore

Backup không được coi là hoàn tất nếu chưa restore thử.

| Thành phần | Backup | Restore test |
|---|---|---|
| PostgreSQL | Encrypted dump/snapshot, lịch backup rõ | Restore vào môi trường test |
| Object storage | Versioning/lifecycle/replication nếu có | Kiểm tra object evidence còn đọc được |
| Model artifact | Lưu version/checksum | Verify checksum và rollback model |
| ANSVIS config | Export cấu hình nếu nền tảng cho phép | Kiểm tra restore point không thiếu face DB/model/license |
| Secret/config | Backup theo secret manager policy | Không export plaintext bừa bãi |

Runbook backup/restore phải nêu:

- RPO/RTO mục tiêu.
- Ai có quyền restore.
- Restore vào đâu.
- Cách xác minh dữ liệu sau restore.
- Cách xử lý nếu key mã hóa bị mất.
- Cách xử lý nếu backup chứa dữ liệu đã phải xóa theo consent.

## Database hardening checklist

Trước staging/production:

- PostgreSQL không public internet.
- Chỉ mở port cần thiết trong private network/firewall.
- Tài khoản app dùng least privilege.
- Không dùng superuser cho app runtime.
- Mật khẩu mạnh, lưu ở secret manager.
- TLS bật nếu hạ tầng hỗ trợ.
- Backup mã hóa.
- Restore drill thành công.
- Slow query log/monitoring bật ở mức phù hợp.
- Migration review trước deploy.
- Không có seed data thật.
- Không có dump thật trong repo.
- Security scan không còn Critical/High chưa xử lý.

## Migration policy

- Mọi thay đổi schema phải qua migration.
- Migration phải review được.
- Migration phải có rollback hoặc kế hoạch khôi phục rõ.
- Không sửa production schema thủ công.
- Không xóa cột/bảng chứa dữ liệu quan trọng nếu chưa có bước deprecate/migrate/archive.
- Migration ảnh hưởng bảng lớn phải có kế hoạch downtime hoặc online migration.
- Trước production migration phải backup.

## Test bắt buộc

| Nhóm test | Kịch bản |
|---|---|
| Migration | Apply migration từ database rỗng và database có dữ liệu mẫu |
| Encryption | Encrypt/decrypt roundtrip, sai key không đọc được, key rotation đọc được dữ liệu cũ |
| Authorization | Parent chỉ thấy con mình, giáo viên chỉ thấy lớp mình, BGH/Admin có audit |
| Consent | Không consent thì block biometric, rút consent thì disable/xóa/anonymize đúng |
| Evidence | Signed URL hết hạn, không có quyền thì không tạo URL |
| Audit | Xem/export/sửa/xóa dữ liệu nhạy cảm đều tạo audit |
| Retention | Dry-run đúng, xóa đúng phạm vi, có audit |
| Backup/restore | Restore encrypted backup vào test environment thành công |
| Log masking | Không có token, secret, face data, base64 image trong log |
| Event idempotency | Event trùng không tạo attendance/violation trùng |

## Task bổ sung cho backlog

| ID | Task | Nhóm | Ưu tiên | Phụ thuộc | Definition of Done |
|---|---|---|---|---|---|
| DBSEC-01 | Hoàn thiện database and encryption plan | DB/Security | Rất cao | Docs baseline | File này được review và được trỏ từ index/agent rules |
| DBSEC-02 | Thiết kế ERD và data dictionary | DB | Rất cao | DBSEC-01 | Có bảng, field, khóa, quan hệ, index chính |
| DBSEC-03 | Data classification theo bảng/field | Security/DB | Rất cao | DBSEC-02 | Mỗi field nhạy cảm có handling rule |
| DBSEC-04 | Thiết kế application-level encryption | Security/Backend | Rất cao | DBSEC-03 | Có danh sách field mã hóa, `key_id`, lookup hash nếu cần |
| DBSEC-05 | Thiết kế key management và rotation | Security/DevOps | Rất cao | DBSEC-04 | Có secret/KMS strategy, rotate/revoke/recovery |
| DBSEC-06 | Thiết kế object storage evidence policy | Backend/Security | Rất cao | DBSEC-03 | Có metadata table, signed URL, TTL, audit |
| DBSEC-07 | Thiết kế audit log schema | Security/DB | Rất cao | DBSEC-02 | Có audit event list và schema tối thiểu |
| DBSEC-08 | Thiết kế retention/delete/anonymize policy | Privacy/DB | Rất cao | DBSEC-03 | Có policy theo loại dữ liệu và dry-run rule |
| DBSEC-09 | Thiết kế backup encryption và restore drill | DevOps/Security | Rất cao | DBSEC-05 | Có backup/restore runbook và checklist kiểm chứng |
| DBSEC-10 | Thiết kế database hardening checklist | Security/DevOps | Cao | DBSEC-09 | Có checklist staging/production |
| DBSEC-11 | Viết test plan cho database/encryption | QA/Security | Cao | DBSEC-04 | Có migration/encryption/auth/retention/backup test matrix |
| DBSEC-12 | Tạo GitHub issues DBSEC | PM/GitHub | Trung bình | DBSEC-01 | Issues có label/milestone, không chứa secret/dữ liệu thật |

## Go-live gate cho database và encryption

Không go-live nếu còn thiếu một trong các mục sau:

- ERD/data dictionary baseline.
- Migration đã chạy được trên staging.
- Backup mã hóa và restore test thành công.
- Object storage private, signed URL TTL hoạt động.
- Log masking kiểm tra đạt.
- Secret scan sạch.
- Permission/object-level authorization test đạt.
- Consent enforcement test đạt.
- Audit log cho dữ liệu nhạy cảm hoạt động.
- Retention job có dry-run và audit.
- Không còn Critical/High security issue chưa xử lý.\n