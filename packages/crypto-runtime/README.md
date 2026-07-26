# crypto-runtime

Thư viện dùng chung triển khai `ENCV1` field encryption và `LOOKUP-V1` exact lookup theo quyết định
#50/#51, phục vụ Issue #134. Package chỉ chứa runtime primitive; không chứa business state, secret,
credential hay environment config.

## Phạm vi

- `ENCV1` envelope AEAD `AES-256-GCM`: magic/version, algorithm, `key_id` non-secret, wrapped DEK,
  nonce 96-bit, ciphertext + tag, `aad_schema`. Mỗi operation dùng DEK và nonce mới.
- `aad_schema=v1` bind ciphertext vào coordinate bất biến: service, `schema.table.field`, record
  UUID, tenant scope. Đổi record/tenant/field hoặc sửa header/ciphertext làm authentication fail.
- `LOOKUP-V1`: HMAC-SHA-256 full-length với lookup key riêng, domain separation bắt buộc theo
  purpose/tenant/normalization version. Không search/index ciphertext.
- `KeyProvider` port với ba adapter: `UnavailableKeyProvider` (mặc định fail-closed),
  `DeterministicFakeKeyProvider` (chỉ cho test/local), `SecretManagerKeyProvider` (seam cho Issue
  #141, fail closed tới khi resolver được inject).
- Helper migration `encv1_prefix_check` / `encv1_check_constraint` để cột `*_ciphertext` bắt buộc có
  ENCV1 prefix thay vì chỉ `octet_length(...) > 0`.

## Không thuộc phạm vi

- Provisioning KMS/HSM thật, key material thật, key ceremony, secret manager provider (Issue #141).
- Áp constraint ENCV1 lên bảng đã migrate (cần migration và change record riêng).
- Thay thế RBAC/ABAC, consent/purpose gate, audit, retention, private object storage hay TLS.

## Error contract

Mọi failure trả stable code đã redact, không kèm plaintext/key/ciphertext:
`ENCRYPTION_KEY_UNAVAILABLE`, `ENCRYPTION_ENVELOPE_INVALID`, `ENCRYPTION_AUTH_FAILED`,
`LOOKUP_NORMALIZATION_INVALID`. Không có nhánh fallback plaintext trong bất kỳ code path nào.

## Rotation

Dual-read/current-write: write luôn dùng `current_key_id()`; read chấp nhận key `active` và
`decrypt_only`; `rewrap()` re-encrypt sang key hiện hành mà không lộ plaintext ra ngoài scope hàm.
Key `disabled` từ chối cả read lẫn write.

## Sử dụng

```python
from camera_ai_crypto import EncryptionService, FieldBinding, UnavailableKeyProvider

service = EncryptionService(key_provider=UnavailableKeyProvider())  # fail closed cho tới khi wire
binding = FieldBinding(
    service="school-service",
    field_path="school.students.full_name_ciphertext",
    record_id=student_id,
    tenant_ref=tenant_ref,
)
envelope = service.encrypt(value_bytes, binding)
```

## Test

```powershell
rtk .\.venv\Scripts\python.exe -m pytest -q packages/crypto-runtime/tests
```

Test dùng fake key và dữ liệu tổng hợp: round-trip, non-determinism, tamper/truncate, AAD mismatch
cross-record/tenant/field/service, plaintext-giả-ciphertext, unwired/disabled key, rotation +
rewrap, redaction của error, domain isolation và normalization của lookup, helper migration.
