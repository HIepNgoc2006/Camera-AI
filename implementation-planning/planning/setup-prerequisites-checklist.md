# Setup prerequisites checklist - cần cài đặt trước khi xây dựng hệ thống

## Mục tiêu

File này liệt kê toàn bộ phần mềm, công cụ, thư viện và dịch vụ cần chuẩn bị trước khi bắt đầu xây dựng hệ thống AI Camera cho trường học.

Nguyên tắc:

- Cài theo thứ tự ưu tiên, không cài tràn lan nếu chưa cần.
- Môi trường local dùng dữ liệu giả/sanitize, không dùng dữ liệu học sinh thật.
- Không lưu `.env` thật, secret, camera credential, face DB, dataset thật hoặc video thật vào Git.
- PostgreSQL là database chính. Không dùng MongoDB làm database nghiệp vụ chính.
- AI custom training/evaluation chỉ dùng dữ liệu từ camera dự án thông qua ANSVIS/AIBOX, trừ khi có phê duyệt riêng.

## Mức ưu tiên

| Mức | Ý nghĩa |
|---|---|
| Bắt buộc trước coding | Cần có trước khi scaffold/code |
| Bắt buộc trước AI/pilot | Cần có trước khi làm ANSVIS/camera/model |
| Bắt buộc trước staging/production | Cần có trước khi deploy môi trường thật |
| Khuyến nghị | Nên có để làm nhanh, dễ kiểm soát, dễ bảo trì |
| Tùy chọn | Chỉ cần khi dự án mở rộng hoặc có yêu cầu nâng cao |

## Máy và hệ điều hành

| Cần cài/chuẩn bị | Mức | Mục đích | Ghi chú |
|---|---|---|---|
| Windows 11 64-bit hoặc Windows 10 64-bit | Bắt buộc trước coding | Môi trường dev chính | Phù hợp ANSVIS/ANSTS |
| RAM tối thiểu 16GB, khuyến nghị 32GB+ | Bắt buộc trước coding | Chạy Docker, backend, web/mobile dev | AI/pilot có thể cần cao hơn |
| SSD trống tối thiểu 100GB | Bắt buộc trước coding | Docker image, DB local, log, artifact | Không lưu dataset thật trong repo |
| GPU NVIDIA | Bắt buộc trước AI/pilot nếu train/chạy AI local | Tăng tốc ANSVIS/ANSTS/model | Cần kiểm driver/CUDA tương thích |
| WSL2 Ubuntu | Khuyến nghị | Môi trường Linux-like trên Windows | Hữu ích cho script/dev tools |
| PowerShell 7 | Khuyến nghị | Shell hiện đại trên Windows | Phù hợp workspace hiện tại |

## Công cụ phát triển cơ bản

| Công cụ | Mức | Mục đích | Ghi chú |
|---|---|---|---|
| Git | Bắt buộc trước coding | Quản lý source code | Cần cấu hình user/email |
| GitHub CLI `gh` | Khuyến nghị | Quản lý repo, issue, PR | Không lưu token trong repo |
| VS Code hoặc JetBrains IDE | Bắt buộc trước coding | Code editor | VS Code đủ dùng |
| Docker Desktop | Bắt buộc trước coding | Chạy local stack | Bật WSL2 backend nếu dùng Windows |
| Docker Compose | Bắt buộc trước coding | Điều phối PostgreSQL/Redis/RabbitMQ/MinIO | Đi kèm Docker Desktop |
| OpenSSL | Khuyến nghị | Tạo key/cert local, test TLS/JWT | Không dùng key local cho production |
| Make hoặc task runner tương đương | Khuyến nghị | Chuẩn hóa lệnh dev/test | Có thể thay bằng PowerShell script |
| 7-Zip | Khuyến nghị | Nén/giải nén artifact | Không nén dataset thật để gửi ngoài quy trình |

## Công cụ kiểm thử API và tài liệu

| Công cụ | Mức | Mục đích | Ghi chú |
|---|---|---|---|
| Bruno/Postman/Insomnia | Khuyến nghị | Test API thủ công | Bruno dễ lưu collection vào repo |
| Swagger UI/ReDoc | Bắt buộc trước coding | Xem OpenAPI | FastAPI có sẵn Swagger UI |
| Spectral | Khuyến nghị | Lint OpenAPI | Dùng khi API contract lớn |
| Markdownlint | Khuyến nghị | Kiểm Markdown docs | Giữ docs dễ đọc |
| Mermaid | Khuyến nghị | Vẽ diagram trong Markdown | Dùng cho flow/architecture |

## Backend runtime và thư viện

| Công cụ/thư viện | Mức | Vai trò |
|---|---|---|
| Python 3.12+ | Bắt buộc trước coding | Runtime backend/worker |
| pip/uv/poetry | Bắt buộc trước coding | Quản lý dependency Python |
| FastAPI | Bắt buộc trước coding | API framework |
| Uvicorn/Gunicorn | Bắt buộc trước coding | Chạy ASGI service |
| Pydantic v2 | Bắt buộc trước coding | Validate request/response/event |
| SQLAlchemy 2.x | Bắt buộc trước coding | ORM/database access |
| Alembic | Bắt buộc trước coding | Database migration |
| asyncpg hoặc psycopg | Bắt buộc trước coding | PostgreSQL driver |
| httpx | Bắt buộc trước coding | HTTP client gọi ANSVIS/service ngoài |
| aio-pika/Celery/RQ | Khuyến nghị | Worker/queue processing |
| python-jose hoặc authlib | Khuyến nghị | JWT/OAuth helper |
| argon2-cffi/bcrypt/passlib | Bắt buộc trước coding | Password hashing |
| structlog hoặc loguru | Khuyến nghị | Structured logging |
| OpenTelemetry SDK | Bắt buộc trước staging/production | Trace/metrics/log correlation |
| pytest | Bắt buộc trước coding | Unit/integration test |
| pytest-asyncio | Bắt buộc trước coding | Async test |
| ruff | Bắt buộc trước coding | Lint/format Python |
| mypy hoặc pyright | Khuyến nghị | Type checking |

## Web Portal

| Công cụ/thư viện | Mức | Vai trò |
|---|---|---|
| Node.js Active LTS | Bắt buộc trước coding | Runtime frontend |
| pnpm hoặc npm | Bắt buộc trước coding | Package manager |
| Next.js | Bắt buộc trước coding | Web Portal framework |
| React | Bắt buộc trước coding | UI library |
| TypeScript | Bắt buộc trước coding | Type safety |
| Tailwind CSS | Khuyến nghị | Styling nhanh, nhất quán |
| shadcn/ui hoặc Ant Design | Khuyến nghị | Component UI |
| TanStack Query | Khuyến nghị | API state/cache |
| React Hook Form | Khuyến nghị | Form |
| Zod | Khuyến nghị | Frontend validation |
| Recharts hoặc ECharts | Khuyến nghị | Dashboard/report chart |
| Vitest | Khuyến nghị | Unit test frontend |
| Playwright | Bắt buộc trước staging/production | E2E Web test |
| ESLint/Prettier | Bắt buộc trước coding | Code quality |

## Mobile App

| Công cụ/thư viện/phần mềm | Mức | Vai trò | Ghi chú |
|---|---|---|---|
| React Native | Bắt buộc trước coding | Mobile iOS/Android một codebase | Theo yêu cầu dự án |
| Expo hoặc React Native CLI | Cần chốt trước coding | Toolchain mobile | Expo nhanh hơn, bare RN linh hoạt hơn |
| Node.js Active LTS | Bắt buộc trước coding | Mobile tooling | Dùng chung Web |
| Android Studio | Bắt buộc trước mobile dev | Android SDK/emulator | Cần cho build/test Android |
| JDK tương thích React Native | Bắt buộc trước mobile dev | Build Android | Pin theo version RN |
| Xcode/macOS | Bắt buộc nếu build iOS local | Build iOS | Windows không build iOS native local |
| EAS Build hoặc CI macOS | Khuyến nghị nếu dùng Expo/iOS | Build iOS cloud/CI | Giảm phụ thuộc máy Mac |
| React Navigation | Bắt buộc trước coding | Điều hướng app |
| TanStack Query | Khuyến nghị | API state/cache |
| expo-secure-store hoặc react-native-keychain | Bắt buộc trước coding | Lưu token an toàn |
| Firebase Cloud Messaging/APNs | Bắt buộc trước notification production | Push notification | Cần tài khoản/config riêng |
| Sentry React Native | Khuyến nghị | Crash/error tracking |
| Jest | Khuyến nghị | Unit test |
| Detox hoặc Maestro | Tùy chọn | Mobile E2E test |

## Database, queue, cache, object storage

| Công cụ/phần mềm | Mức | Vai trò | Ghi chú |
|---|---|---|---|
| PostgreSQL 16+ | Bắt buộc trước coding | Database nghiệp vụ chính | Có thể chạy Docker local hoặc tự host |
| pgAdmin/DBeaver/TablePlus | Khuyến nghị | Inspect database | Không dùng để sửa production thủ công |
| Redis 7+ | Bắt buộc trước coding | Cache, rate limit, distributed lock | Chạy Docker local |
| RabbitMQ | Bắt buộc trước coding | Queue event/retry/DLQ | Chạy Docker local |
| MinIO | Bắt buộc trước coding | S3-compatible object storage local | Lưu evidence/model/backup local giả lập |
| S3-compatible storage production | Bắt buộc trước production | Lưu evidence/model/backup | Bucket private, signed URL |
| pg_dump/pg_restore | Bắt buộc trước staging/production | Backup/restore PostgreSQL | Cần test restore |
| Alembic | Bắt buộc trước coding | Migration | Đã liệt kê ở backend nhưng nhắc lại vì bắt buộc |

Không cài MongoDB làm database chính. Nếu sau này cần analytics/event search riêng, chỉ nghiên cứu như hệ phụ, không thay PostgreSQL core.

## AI, ANSVIS, camera tooling

| Công cụ/phần mềm | Mức | Vai trò | Ghi chú |
|---|---|---|---|
| ANSVIS/AIBOX | Bắt buộc trước AI/pilot | Video analytics, AI Task, Event Log, HTTP Trigger | Theo yêu cầu tích hợp |
| ANSTS | Tùy chọn/Bắt buộc chỉ khi cần custom model | Label/train/evaluate/export model | Dùng khi built-in/prebuilt task không đạt; dữ liệu từ camera dự án qua ANSVIS/AIBOX |
| ODHUB | Tùy chọn | Object detection training no-code | Chỉ dùng nếu phù hợp task |
| NVIDIA Driver | Bắt buộc nếu dùng GPU NVIDIA | GPU acceleration | Pin theo GPU/ANSVIS/ANSTS |
| CUDA/cuDNN tương thích | Bắt buộc nếu tool AI yêu cầu | GPU runtime | Không tự nâng version nếu chưa kiểm |
| FFmpeg | Khuyến nghị | Kiểm video/stream/sample | Hữu ích khi test ANSVIS |
| VLC | Khuyến nghị | Test RTSP thủ công | Không lưu credential trong screenshot/log |
| ONVIF Device Manager | Khuyến nghị | Kiểm camera ONVIF trong LAN | Chỉ dùng với mạng được phép |
| OpenCV Python | Khuyến nghị | Tiền xử lý/test ảnh/video phụ trợ | Không xử lý dữ liệu thật ngoài quy trình |
| Label Studio/CVAT | Tùy chọn | Label bổ trợ nếu ANSTS không đủ | Chỉ chạy private/local nếu có dữ liệu thật |
| MLflow hoặc DVC | Tùy chọn/Khuyến nghị nếu training nhiều | Model/dataset version tracking | Không commit dataset thật |

Quy tắc AI data:

- Training/fine-tune/evaluation không phải scope mặc định; chỉ thực hiện nếu built-in/prebuilt task không đạt.
- Nếu có training/fine-tune/evaluation, dữ liệu chỉ lấy từ camera dự án thông qua ANSVIS/AIBOX.
- Không dùng dataset ngoài/Internet/trường khác mặc định.
- Không đưa dataset ANSVIS/camera lên cloud training nếu chưa có phê duyệt, mã hóa, audit và consent/căn cứ pháp lý rõ.
- Dataset thật không nằm trong Git.
- Model artifact phải có version, checksum, dataset hash, metric và approval.

## Security tooling

| Công cụ | Mức | Vai trò |
|---|---|---|
| gitleaks | Bắt buộc trước coding | Scan secret trong repo |
| Semgrep | Bắt buộc trước staging/production | Static security scan |
| pip-audit | Bắt buộc trước staging/production | Scan dependency Python |
| npm audit/pnpm audit | Bắt buộc trước staging/production | Scan dependency JS |
| Trivy | Bắt buộc trước staging/production | Scan container image/IaC |
| OWASP ZAP baseline | Bắt buộc trước production | Scan Web/API cơ bản |
| Infisical/Doppler/Vault/Cloud Secret Manager | Bắt buộc trước staging/production | Secret management |
| SOPS/age | Khuyến nghị | Encrypt config nếu cần lưu trong repo |
| Dependabot/Renovate | Khuyến nghị | Theo dõi dependency update |
| Pre-commit hooks | Khuyến nghị | Chạy lint/secret scan trước commit |

Security rule:

- Local chỉ dùng `.env.example` và `.env` local giả lập.
- Không đọc/in/paste `.env` thật.
- Không commit secret, private key, camera credential, license key, face DB export, database dump.

## Observability và vận hành

| Công cụ | Mức | Vai trò |
|---|---|---|
| Prometheus | Bắt buộc trước production | Metrics |
| Grafana | Bắt buộc trước production | Dashboard |
| Loki hoặc OpenSearch | Khuyến nghị | Log aggregation |
| OpenTelemetry Collector | Khuyến nghị/Bắt buộc nếu tracing nghiêm túc | Trace/log/metric pipeline |
| Sentry | Khuyến nghị | Error/crash tracking backend/web/mobile |
| Uptime Kuma | Khuyến nghị | Health monitoring đơn giản |
| Nginx hoặc Traefik | Bắt buộc trước staging/production | Reverse proxy/TLS/routing |
| Certbot hoặc managed certificate | Bắt buộc trước production | TLS certificate |

Metric/alert cần chuẩn bị:

- API latency/error rate.
- Login fail spike.
- ANSVIS task status.
- Event ingestion rate.
- Queue depth/DLQ.
- Storage usage.
- Export spike.
- Backup success/failure.
- CPU/RAM/GPU/disk.

## CI/CD, GitHub và quản lý tiến độ

| Công cụ/dịch vụ | Mức | Vai trò |
|---|---|---|
| GitHub repo | Bắt buộc trước coding | Source control, Issues, milestones |
| GitHub Issues | Bắt buộc trước coding | Theo dõi task/security/test/risk |
| GitHub Projects | Khuyến nghị | Board theo dõi tiến độ cho sếp |
| GitHub Actions | Bắt buộc trước staging | CI test/scan/build |
| Conventional Commits | Khuyến nghị | Commit dễ đọc |
| Pull Request template | Khuyến nghị | Chuẩn hóa review/security checklist |
| Issue templates | Khuyến nghị | Bug/security/task rõ ràng |

## MCP/coding assistant hỗ trợ

| MCP/tool | Mức | Vai trò | Lưu ý bảo mật |
|---|---|---|---|
| Filesystem tool | Bắt buộc | Đọc/sửa file trong workspace | Không cấp quyền ngoài phạm vi repo nếu không cần |
| Shell tool | Bắt buộc | Chạy test/lint/script | Không in secret |
| Git tool | Khuyến nghị | Xem status/diff/history | Không commit secret |
| GitHub MCP/CLI | Khuyến nghị | Quản lý issue/PR/project | Cần token quyền tối thiểu |
| PostgreSQL MCP | Khuyến nghị khi có DB | Inspect schema/query | Không dùng với production DB nếu chưa được phép |
| Playwright MCP | Khuyến nghị khi làm Web | Test UI tự động | Không dùng account thật |
| OpenAPI tooling | Khuyến nghị | Kiểm API contract/client | Dùng schema đã sanitize |
| Docker/log tool | Khuyến nghị | Xem container/log | Log phải mask dữ liệu nhạy cảm |
| Grafana/Sentry MCP | Tùy chọn production | Debug vận hành | Chỉ cấp quyền read-only nếu có thể |

Không cấp MCP quyền đọc secret production, `.env` thật, database thật, face DB, object storage chứa dữ liệu thật hoặc camera credential nếu chưa có phê duyệt.

## Tài khoản/dịch vụ cần chuẩn bị

| Tài khoản/dịch vụ | Mức | Dùng cho | Ghi chú |
|---|---|---|---|
| GitHub account/repo access | Bắt buộc trước coding | Source, issues, CI | Dùng MFA |
| Docker Hub/GitHub Container Registry | Khuyến nghị | Lưu image | Không public image chứa config nhạy cảm |
| Firebase project | Bắt buộc trước notification production | Push notification Android/iOS | Không commit service account |
| Apple Developer Account | Bắt buộc nếu phát hành iOS | iOS build/publish | Cần khi lên store/TestFlight |
| Google Play Console | Bắt buộc nếu phát hành Android | Android publish | Cần khi phát hành thật |
| Domain/subdomain | Bắt buộc trước production | Web/API endpoint | Cần TLS |
| Email/SMS provider | Tùy chọn/tuỳ yêu cầu | OTP/email notification | Không gửi dữ liệu nhạy cảm |
| S3-compatible storage account | Bắt buộc trước production | Evidence/model/backup | Private bucket |
| Secret manager account | Bắt buộc trước staging/production | Quản lý secret | Infisical/Doppler/Vault/cloud |

## Checklist cài đặt theo thứ tự

### Giai đoạn 1 - đủ để bắt đầu scaffold/code

- Windows 10/11 64-bit.
- Git.
- GitHub CLI.
- IDE.
- Docker Desktop + Docker Compose.
- Python 3.12+.
- Node.js Active LTS.
- pnpm hoặc npm.
- PostgreSQL client/DBeaver.
- gitleaks.
- FFmpeg/VLC.
- Bruno/Postman/Insomnia.

### Giai đoạn 2 - dựng local backend stack

- PostgreSQL container.
- Redis container.
- RabbitMQ container.
- MinIO container.
- FastAPI dependencies.
- SQLAlchemy/Alembic.
- pytest/pytest-asyncio.
- ruff.
- OpenAPI/Swagger.

### Giai đoạn 3 - dựng Web/Mobile

- Next.js/React/TypeScript.
- Tailwind CSS.
- UI component library.
- TanStack Query.
- React Hook Form/Zod.
- Playwright.
- React Native/Expo hoặc React Native CLI.
- Android Studio.
- JDK tương thích.
- Secure storage library cho mobile.

### Giai đoạn 4 - chuẩn bị ANSVIS/AI pilot

- ANSVIS/AIBOX.
- ANSTS nếu cần custom model.
- NVIDIA driver/CUDA nếu dùng GPU.
- VLC/ONVIF Device Manager.
- Dataset manifest template.
- Quy trình export sample từ ANSVIS.
- Nơi lưu dataset/model mã hóa, không nằm trong Git.

### Giai đoạn 5 - trước staging/production

- Secret manager.
- Semgrep.
- pip-audit.
- npm/pnpm audit.
- Trivy.
- OWASP ZAP baseline.
- Prometheus.
- Grafana.
- Log aggregation.
- OpenTelemetry Collector nếu dùng tracing.
- Sentry nếu dùng crash/error tracking.
- Nginx/Traefik.
- TLS certificate.
- Backup/restore tooling.
- GitHub Actions CI/CD.

## Bộ cài tối thiểu nếu muốn bắt đầu nhanh

Nếu chỉ cần bắt đầu scaffold codebase an toàn, cài tối thiểu:

- Git.
- GitHub CLI.
- VS Code.
- Docker Desktop.
- Python 3.12+.
- Node.js Active LTS.
- pnpm.
- PostgreSQL client/DBeaver.
- gitleaks.
- Bruno/Postman.

Sau đó local stack có thể chạy bằng Docker Compose:

- PostgreSQL.
- Redis.
- RabbitMQ.
- MinIO.

## Những thứ chưa nên cài/mua vội

| Không nên vội | Lý do |
|---|---|
| Kubernetes | Chưa cần nếu Docker Compose/VM đủ |
| MongoDB | Không dùng làm database chính |
| ClickHouse/OpenSearch analytics | Chỉ cần khi event/report rất lớn |
| Paid APM lớn | Có thể dùng Grafana/Sentry trước |
| Cloud GPU training | Không dùng mặc định vì dữ liệu camera/ANSVIS nhạy cảm |
| Dataset bên ngoài | Không đúng hướng đã chốt nếu chưa có phê duyệt riêng |

## Definition of Ready trước khi code

Trước khi bắt đầu code, nên có tối thiểu:

- Máy dev cài đủ bộ tối thiểu.
- Docker chạy được.
- Repo GitHub truy cập được.
- `.env.example` có placeholder, không có `.env` thật trong Git.
- gitleaks chạy được.
- PostgreSQL/Redis/RabbitMQ/MinIO local có thể khởi động bằng Docker Compose.
- Python/Node package manager hoạt động.
- Quy tắc PostgreSQL, security, ANSVIS/AI và Agent đã được đọc.
- Không cần dữ liệu thật để bắt đầu scaffold.
