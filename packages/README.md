# Shared packages

Chứa contract và thư viện dùng chung có ownership rõ, ví dụ API/event DTO, security policy helper và observability primitives.

- Không chứa business state, secret, credential hoặc environment-specific config.
- Không dùng shared package để cho service đọc chéo database hoặc bỏ qua API Gateway.
- Tránh đưa business rule của nhiều domain vào một package dùng chung.
- Mọi contract phải có version và test tương thích khi được triển khai.

Thư viện runtime hiện có:

- `crypto-runtime/`: `ENCV1` field encryption (AES-256-GCM envelope, AAD binding, dual-read
  rotation) và `LOOKUP-V1` exact lookup HMAC có domain separation, kèm `KeyProvider` port fail
  closed và helper CHECK cho migration; không chứa key material, secret hay business state.
- `metrics-runtime/`: registry `metrics_registry_v1` (nguồn duy nhất của metric/label vocabulary,
  cardinality chặn từ cấu trúc) và `PrometheusMetricsSink` + internal loopback-only scrape server;
  label không bao giờ chứa identifier.

Các contract hiện có:

- `consent-withdrawal-policy/consent-withdrawal-policy-v1.json`: policy versioned cho authority,
  deny-before-dispose, owner disposition, legal hold/lawful basis, reconciliation/restore và
  completion evidence; runtime/destructive activation vẫn fail closed tới khi đủ named approval và
  change record riêng.
- `evidence-access-policy/evidence-access-policy-v1.json`: policy versioned cho metadata, thumbnail,
  original, download/export, object authorization, signed GET TTL và audit; runtime activation vẫn
  fail closed tới khi đủ named approval.
- `notification-privacy-policy/notification-privacy-policy-v1.json`: policy versioned cho in-app,
  push/email minimization, recipient/object re-authorization, endpoint protection, retry/DLQ,
  cancellation và audit; runtime activation vẫn fail closed tới khi đủ named approval.
- `time-policy/time-policy-v1.json`: policy versioned cho UTC/IANA, clock health và replay window;
  không chứa cấu hình endpoint hoặc secret theo môi trường.
- `ansvis-event-contract/`: JSON Schema, Bearer source auth/replay/idempotency policy và contract ACK
  versioned cho HTTP Trigger; không chứa endpoint runtime, secret, media hoặc raw ANSVIS payload.
