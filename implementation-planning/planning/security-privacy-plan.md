# Security and privacy plan

## Nguyên tắc

Hệ thống dùng trong trường học nên xem dữ liệu trẻ em và khuôn mặt là dữ liệu cực kỳ nhạy cảm. Bảo mật phải được kiểm soát trong thiết kế, code, test, deploy và vận hành.

Nguyên tắc bắt buộc:

- Least privilege: ai cần gì mới được cấp quyền đó.
- Privacy by design: chỉ thu thập dữ liệu cần thiết.
- Consent first: dữ liệu sinh trắc học phải có đồng ý hợp lệ.
- Audit everything sensitive: xem, sửa, xóa, export, đổi quyền đều phải có audit.
- No secret in code: không hard-code hoặc commit secret.
- No raw biometric in logs: không log ảnh mặt, face embedding, base64 image.

## Phân loại dữ liệu

| Dữ liệu | Mức nhạy cảm | Kiểm soát |
|---|---:|---|
| Face image/face crop/face embedding | Rất cao | Consent, mã hóa, truy cập hạn chế, audit |
| Học sinh/phụ huynh/lớp | Rất cao | RBAC/ABAC, object-level authorization |
| Điểm danh/chấm công | Cao | Audit, retention, phân quyền |
| Event snapshot/video | Cao | Private storage, signed URL, watermark/export audit |
| Log/trace/error | Trung bình/Cao | Masking, retention, quyền đọc hạn chế |
| `.env`, key, token, license | Rất cao | Secret manager, rotation, gitleaks |

## Identity & permission

- MFA bắt buộc cho Admin/BGH/tài khoản vận hành.
- RBAC theo vai trò: Admin, BGH, Giáo viên, Phụ huynh, Nhân sự bếp, Auditor.
- ABAC theo ngữ cảnh:
  - Phụ huynh chỉ xem con mình.
  - Giáo viên chỉ xem lớp được phân công.
  - BGH xem phạm vi trường.
- Mọi API trả dữ liệu học sinh phải có object-level authorization.
- Token có expiry, refresh token có revoke.

### Baseline role/object permission matrix

Ma trận dưới đây là baseline fail-closed để thiết kế API và test. Ký hiệu `Phạm vi` luôn yêu cầu object-level authorization; ô `Không` là mặc định từ chối. Quyền xem evidence không đồng nghĩa quyền export.

| Vai trò | Tài khoản/quyền | Hồ sơ trường | Điểm danh/chấm công | Vi phạm/evidence | Consent | Report/export | Ops health | Audit |
|---|---|---|---|---|---|---|---|---|
| System Admin | Quản lý theo quy trình, MFA, audit | Quản lý cấu hình; không mặc định xem toàn bộ dữ liệu nghiệp vụ | Không mặc định | Không mặc định | Quản trị cấu hình, không tự thay consent thay chủ thể | Chỉ khi có quyền riêng và audit | Xem health/config đã masking | Xem theo nhiệm vụ được cấp |
| BGH | Không quản trị system role | Phạm vi toàn trường | Xem/duyệt theo trường | Review theo trường; evidence cần policy được duyệt | Xem trạng thái tổng hợp cần thiết | Export theo phạm vi, lý do và audit | Dashboard tổng hợp | Không mặc định xem log kỹ thuật đầy đủ |
| Giáo viên | Không | Lớp được phân công | Xem/chỉnh theo workflow lớp được giao | Chỉ sự kiện học sinh/lớp được giao nếu nghiệp vụ cho phép | Không sửa; chỉ xem trạng thái tối thiểu khi cần | Báo cáo lớp được giao; export phải audit | Không | Không |
| Phụ huynh | Quản lý session/thiết bị của chính mình | Chỉ hồ sơ con liên kết hợp lệ | Chỉ dữ liệu con mình | Chỉ thông tin đã được policy cho phép; không mặc định xem raw face/evidence | Đồng ý/rút consent cho chủ thể hợp lệ theo quy trình | Không export diện rộng | Không | Không |
| Quản lý bếp | Không | Không | Chỉ timekeeping cá nhân nếu được cấp | Chỉ sự kiện PPE trong khu bếp/ca được giao | Không | Báo cáo PPE phạm vi bếp nếu được cấp | Trạng thái khu bếp tối thiểu | Không |
| Vận hành | Quản lý health/session kỹ thuật theo nhiệm vụ | Không | Không | Không xem nội dung evidence; chỉ metadata health đã masking | Không | Không | Camera/task/queue/storage/backup health | Log kỹ thuật đã redaction, không PII/biometric |
| Auditor | Không thay đổi | Read-only theo phạm vi kiểm toán | Read-only theo phạm vi | Metadata/evidence chỉ khi ticket/phê duyệt cho phép | Read-only lịch sử thay đổi | Read-only/export kiểm toán có audit | Read-only khi cần | Read-only, chống sửa/xóa |

### Object attributes bắt buộc

- `school_id` cho mọi dữ liệu nghiệp vụ trường học.
- `class_id`/assignment cho quyền giáo viên.
- Quan hệ `parent_id -> student_id` còn hiệu lực cho phụ huynh.
- `kitchen_zone_id`/shift assignment cho nhân sự bếp.
- `purpose`, `consent_status`, `valid_from`, `withdrawn_at` cho biometric.
- `evidence_sensitivity`, `retention_until`, `review_status` cho media/sự kiện.
- Mọi thay đổi role, assignment, consent, correction, review và export phải có actor, request ID, reason và audit event.

### Điểm cần khách hàng/pháp lý xác nhận

- BGH có được xem raw evidence hay chỉ snapshot đã che/masking.
- Giáo viên được sửa điểm danh trực tiếp hay phải gửi yêu cầu duyệt.
- Phụ huynh được xem snapshot nào, trong bao lâu và có được tải xuống hay không.
- Quản lý bếp được xem danh tính cá nhân hay chỉ thống kê/sự kiện PPE.
- Auditor nào được xem evidence và quy trình ticket/phê duyệt tương ứng.

Không mở rộng quyền khi các điểm trên chưa được xác nhận; implementation và test dùng phương án hạn chế hơn.

## API and network security

- API Gateway là entrypoint duy nhất.
- HTTPS/TLS bắt buộc.
- Nội bộ service dùng service token hoặc mTLS nếu hạ tầng cho phép.
- Rate limit cho login, export, event ingestion, notification.
- CORS allowlist.
- Body size limit cho webhook/upload.
- Không expose service nội bộ ra internet.

## `.env` và secret

Trong repo chỉ có:

```text
.env.example
.env.local.example
.env.staging.example
.env.production.example
```

Không commit:

```text
.env
.env.local
.env.production
*.pem
*.key
*service-account*.json
license key
RTSP URL có username/password thật
face DB export
database dump thật
```

Production secret phải nằm trong secret manager như Infisical, Doppler, Vault hoặc cloud secret manager.

## Data protection

- Thiết kế chi tiết về PostgreSQL, mã hóa, key management, object storage, backup, retention và hardening nằm trong `database-and-encryption-plan.md`. File này là nguồn chuẩn khi code database hoặc xử lý dữ liệu nhạy cảm.
- PostgreSQL encryption at rest ở tầng disk/volume.
- Object storage private.
- Ảnh/video chỉ truy cập bằng signed URL ngắn hạn.
- Không lưu ảnh/video binary trong PostgreSQL.
- Export dữ liệu phải có audit: ai export, lúc nào, lý do.
- Dữ liệu training phải có manifest, checksum và retention.

## Security gates

| Gate | Điều kiện |
|---|---|
| Before coding | Data classification, threat model, `.env.example`, secret policy |
| Before business/API coding | Role/object permission matrix, consent decision, error/API contract và fake/sanitized fixture đã có evidence |
| Before database coding | Đã đọc `database-and-encryption-plan.md`, xác định field nhạy cảm, encryption, audit, retention |
| Before merge | Test, lint, secret scan, permission check |
| Before staging | Dependency scan, migration review, log masking |
| Before production | OWASP review, ZAP baseline, backup/restore, rollback plan |
| After go-live | Monitoring, incident response, access review định kỳ |

## Incident response

Quy trình khi nghi ngờ rò rỉ dữ liệu:

1. Phát hiện và ghi nhận thời gian/scope.
2. Cô lập nguồn rò rỉ: revoke token, tắt endpoint, khóa bucket, stop integration nếu cần.
3. Bảo toàn evidence: log, audit, request ID, event ID.
4. Đánh giá dữ liệu bị ảnh hưởng.
5. Khắc phục: rotate secret, patch code/config, xóa link public.
6. Thông báo nhà trường/phụ huynh theo quy trình đã thống nhất nếu có rò rỉ dữ liệu cá nhân.
7. Postmortem và cập nhật kiểm soát.
