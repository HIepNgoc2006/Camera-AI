# Shared packages

Chứa contract và thư viện dùng chung có ownership rõ, ví dụ API/event DTO, security policy helper và observability primitives.

- Không chứa business state, secret, credential hoặc environment-specific config.
- Không dùng shared package để cho service đọc chéo database hoặc bỏ qua API Gateway.
- Tránh đưa business rule của nhiều domain vào một package dùng chung.
- Mọi contract phải có version và test tương thích khi được triển khai.

Các contract hiện có:

- `time-policy/time-policy-v1.json`: policy versioned cho UTC/IANA, clock health và replay window;
  không chứa cấu hình endpoint hoặc secret theo môi trường.
