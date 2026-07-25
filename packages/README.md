# Shared packages

Chứa contract và thư viện dùng chung có ownership rõ, ví dụ API/event DTO, security policy helper và observability primitives.

- Không chứa business state, secret, credential hoặc environment-specific config.
- Không dùng shared package để cho service đọc chéo database hoặc bỏ qua API Gateway.
- Tránh đưa business rule của nhiều domain vào một package dùng chung.
- Mọi contract phải có version và test tương thích khi được triển khai.

Các contract hiện có:

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
