# Tooling requirements - công cụ, thư viện và phần mềm cần chuẩn bị

## Mục tiêu

File này liệt kê những công cụ, thư viện, phần mềm và dịch vụ hỗ trợ cần chuẩn bị trước khi bắt đầu code hệ thống AI Camera trường học.

Nguyên tắc chọn:

- Ưu tiên công cụ ổn định, dễ bàn giao, nhiều tài liệu.
- Không chọn công nghệ chỉ vì mới.
- Công cụ nào liên quan bảo mật, dữ liệu trẻ em, camera hoặc AI phải có cách audit/backup/kiểm soát rõ.
- Version chính xác sẽ được pin trong repo khi scaffold codebase; ở tài liệu này dùng mốc `LTS` hoặc `x+` để tránh lỗi thời.

## Mức ưu tiên

| Mức | Ý nghĩa |
|---|---|
| Bắt buộc - trước coding | Cần có trước khi bắt đầu scaffold/code |
| Bắt buộc - trước staging/production | Chưa cần ngay ngày đầu, nhưng phải có trước khi test/deploy thật |
| Khuyến nghị | Nên có để làm việc nhanh, sạch, dễ bảo trì |
| Tùy chọn | Dùng khi dự án lớn hơn hoặc có yêu cầu nâng cao |

## Máy dev cần chuẩn bị

| Công cụ/phần mềm | Mức | Mục đích | Ghi chú |
|---|---|---|---|
| Windows 11 hoặc Windows 10 64-bit | Bắt buộc - trước coding | Môi trường chính hiện tại | Phù hợp ANSVIS/ANSTS |
| Git | Bắt buộc - trước coding | Quản lý source code | Cần cấu hình user/email |
| VS Code hoặc JetBrains IDE | Bắt buộc - trước coding | Code editor | VS Code đủ dùng |
| Docker Desktop | Bắt buộc - trước coding | Chạy PostgreSQL, Redis, RabbitMQ, MinIO local | Cần bật WSL2 backend nếu dùng Windows |
| WSL2 Ubuntu | Khuyến nghị | Shell/dev tooling Linux-like | Giúp chạy script/dev tools ổn hơn |
| PowerShell 7 | Khuyến nghị | Script Windows hiện đại | Hợp với workspace hiện tại |
| OpenSSL | Khuyến nghị | Tạo key/cert local, test TLS/JWT | Không dùng key local cho production |
| FFmpeg | Khuyến nghị | Kiểm tra video/camera sample | Hữu ích khi test video/ANSVIS |
| VLC | Khuyến nghị | Test RTSP/video thủ công | Dễ kiểm nhanh camera stream |
| Postman/Insomnia/Bruno | Khuyến nghị | Test API thủ công | Bruno dễ lưu collection trong repo |

## Backend stack

| Công cụ/thư viện | Mức | Vai trò |
|---|---|---|
| Python 3.12+ | Bắt buộc - trước coding | Runtime backend/worker |
| FastAPI | Bắt buộc - trước coding | API framework |
| Uvicorn/Gunicorn | Bắt buộc - trước coding | Chạy ASGI app |
| Pydantic v2 | Bắt buộc - trước coding | Validate request/event/schema |
| SQLAlchemy 2.x | Bắt buộc - trước coding | ORM/database access |
| Alembic | Bắt buộc - trước coding | Database migration |
| asyncpg hoặc psycopg | Bắt buộc - trước coding | PostgreSQL driver |
| httpx | Bắt buộc - trước coding | HTTP client gọi service ngoài |
| aio-pika/Celery/RQ | Khuyến nghị | Worker/queue processing |
| python-jose hoặc authlib | Khuyến nghị | JWT/OAuth helper |
| passlib/argon2-cffi/bcrypt | Bắt buộc - trước coding | Password hashing |
| structlog hoặc loguru | Khuyến nghị | Structured logging |
| OpenTelemetry SDK | Bắt buộc - trước staging/production | Trace/metrics/log correlation |
| pytest | Bắt buộc - trước coding | Unit/integration test |
| pytest-asyncio | Bắt buộc - trước coding | Async test |
| ruff | Bắt buộc - trước coding | Lint/format Python |
| mypy hoặc pyright | Khuyến nghị | Type checking |

## Web Portal stack

| Công cụ/thư viện | Mức | Vai trò |
|---|---|---|
| Node.js Active LTS | Bắt buộc - trước coding | Runtime frontend |
| pnpm hoặc npm | Bắt buộc - trước coding | Package manager |
| Next.js | Bắt buộc - trước coding | Web Portal framework |
| React | Bắt buộc - trước coding | UI library |
| TypeScript | Bắt buộc - trước coding | Type safety |
| Tailwind CSS | Khuyến nghị | Styling nhanh, nhất quán |
| shadcn/ui hoặc Ant Design | Khuyến nghị | Component UI |
| TanStack Query | Khuyến nghị | API state/cache |
| React Hook Form | Khuyến nghị | Form |
| Zod | Khuyến nghị | Frontend validation |
| Recharts hoặc ECharts | Khuyến nghị | Dashboard/report charts |
| Vitest | Khuyến nghị | Unit test frontend |
| Playwright | Bắt buộc - trước staging/production | E2E Web test |
| ESLint/Prettier | Bắt buộc - trước coding | Code quality |

## Mobile App stack

| Công cụ/thư viện/phần mềm | Mức | Vai trò | Ghi chú |
|---|---|---|---|
| React Native | Bắt buộc - trước coding | Mobile iOS/Android một codebase | Theo yêu cầu dự án |
| Expo hoặc React Native CLI | Cần chốt trước coding | Toolchain mobile | Expo nhanh hơn; bare RN linh hoạt hơn |
| Node.js Active LTS | Bắt buộc - trước coding | Mobile build tooling | Dùng chung Web |
| Android Studio | Bắt buộc - trước mobile dev | Android SDK/emulator | Cần cho build/test Android |
| JDK tương thích React Native | Bắt buộc - trước mobile dev | Build Android | Pin version theo RN version |
| Xcode/macOS | Bắt buộc nếu build iOS local | Build iOS | Windows không build iOS native local được |
| EAS Build hoặc CI macOS | Khuyến nghị nếu dùng Expo/iOS | Build iOS cloud/CI | Giảm phụ thuộc máy Mac |
| React Navigation | Bắt buộc - trước coding | Điều hướng app |
| TanStack Query | Khuyến nghị | API state/cache |
| expo-secure-store hoặc react-native-keychain | Bắt buộc - trước coding | Lưu token an toàn |
| Firebase Cloud Messaging/APNs | Bắt buộc - trước notification production | Push notification | Cần tài khoản/config riêng |
| Sentry React Native | Khuyến nghị | Crash/error tracking |
| Jest | Khuyến nghị | Unit test |
| Detox hoặc Maestro | Tùy chọn | Mobile E2E test |

## Database, queue, storage

| Công cụ/phần mềm | Mức | Vai trò |
|---|---|---|
| PostgreSQL 16+ | Bắt buộc - trước coding | Database nghiệp vụ chính |
| pgAdmin/DBeaver/TablePlus | Khuyến nghị | Inspect database |
| Redis 7+ | Bắt buộc - trước coding | Cache, rate limit, lock |
| RabbitMQ | Bắt buộc - trước coding | Queue event/retry/DLQ |
| MinIO | Bắt buộc - trước coding | S3-compatible object storage local |
| S3-compatible storage production | Bắt buộc - trước production | Lưu evidence/model/backup |
| Alembic | Bắt buộc - trước coding | Migration |
| Database backup tool | Bắt buộc - trước staging/production | Backup/restore PostgreSQL |

Không dùng MongoDB làm database chính cho dữ liệu nghiệp vụ trường học. Nếu sau này event analytics quá lớn, có thể nghiên cứu thêm ClickHouse/MongoDB/OpenSearch cho mục tiêu phụ, không thay PostgreSQL core.

## AI, ANSVIS, camera tooling

| Công cụ/phần mềm | Mức | Vai trò |
|---|---|---|
| ANSVIS/AIBOX | Bắt buộc theo yêu cầu tích hợp | Video analytics, AI Task, Event Trigger |
| ANSTS | Tùy chọn/Bắt buộc chỉ khi cần custom model | Label/train/evaluate/export model khi built-in/prebuilt task không đạt |
| ODHUB | Tùy chọn | Object detection training no-code nếu phù hợp |
| NVIDIA Driver/CUDA tương thích | Bắt buộc nếu máy AI dùng NVIDIA GPU | GPU acceleration |
| FFmpeg | Khuyến nghị | Kiểm tra video stream/sample |
| VLC | Khuyến nghị | Test RTSP thủ công |
| ONVIF Device Manager | Khuyến nghị | Kiểm tra camera ONVIF trong LAN |
| OpenCV Python | Khuyến nghị | Tiền xử lý/test ảnh/video phụ trợ |
| Label Studio/CVAT | Tùy chọn | Label bổ trợ nếu ANSTS không đủ |
| MLflow hoặc DVC | Tùy chọn/Khuyến nghị nếu training nhiều | Model/dataset version tracking |

Lưu ý bảo mật:

- Dữ liệu training/fine-tune/kiểm định AI chỉ lấy từ camera dự án thông qua ANSVIS/AIBOX theo xác nhận từ cấp trên.
- Không lưu video/crop mặt thật vào repo.
- Không export face DB/model/dataset ra máy cá nhân nếu chưa có quy trình.
- Không đưa dataset ANSVIS/camera lên cloud training hoặc dịch vụ ngoài nếu chưa có phê duyệt, mã hóa, audit và điều kiện pháp lý/consent rõ.
- ANSVIS Debug Mode chỉ bật khi test, không bật production.
- Payload HTTP Trigger nên tối giản và có auth.

## Security tooling

| Công cụ | Mức | Vai trò |
|---|---|---|
| gitleaks | Bắt buộc - trước coding | Scan secret trong repo |
| Semgrep | Bắt buộc - trước staging/production | Static security scan |
| pip-audit | Bắt buộc - trước staging/production | Scan dependency Python |
| npm audit/pnpm audit | Bắt buộc - trước staging/production | Scan dependency JS |
| Trivy | Bắt buộc - trước staging/production | Scan container image/IaC |
| OWASP ZAP baseline | Bắt buộc - trước production | Scan Web/API cơ bản |
| Infisical/Doppler/Vault/Cloud Secret Manager | Bắt buộc - trước staging/production | Secret management |
| SOPS/age | Khuyến nghị | Encrypt config nếu cần lưu trong repo |
| Dependabot/Renovate | Khuyến nghị | Theo dõi dependency update |

## Observability and operations

| Công cụ | Mức | Vai trò |
|---|---|---|
| Prometheus | Bắt buộc - trước production | Metrics |
| Grafana | Bắt buộc - trước production | Dashboard |
| Loki hoặc OpenSearch | Khuyến nghị | Log aggregation |
| OpenTelemetry Collector | Khuyến nghị/Bắt buộc nếu tracing nghiêm túc | Trace/log/metric pipeline |
| Sentry | Khuyến nghị | Error/crash tracking backend/web/mobile |
| Uptime Kuma | Khuyến nghị | Health monitoring đơn giản |
| Nginx hoặc Traefik | Bắt buộc - trước staging/production | Reverse proxy/TLS/routing |
| Certbot hoặc managed certificate | Bắt buộc - trước production | TLS certificate |

## API, docs, contract tooling

| Công cụ | Mức | Vai trò |
|---|---|---|
| OpenAPI/Swagger | Bắt buộc - trước coding | API contract |
| Swagger UI/ReDoc | Khuyến nghị | Xem API docs |
| Bruno/Postman/Insomnia | Khuyến nghị | API collection |
| openapi-typescript | Khuyến nghị | Sinh type client frontend |
| Spectral | Khuyến nghị | Lint OpenAPI |
| Mermaid | Khuyến nghị | Diagram trong Markdown |
| Markdownlint | Khuyến nghị | Lint docs |

## CI/CD và repo quality

| Công cụ | Mức | Vai trò |
|---|---|---|
| GitHub/GitLab repository | Bắt buộc - trước coding | Source control |
| GitHub Actions/GitLab CI | Bắt buộc - trước staging | CI test/scan/build |
| Docker Compose | Bắt buộc - trước coding | Local/staging stack |
| Dockerfile chuẩn từng service | Bắt buộc - trước staging | Build service |
| Conventional Commits | Khuyến nghị | Commit dễ đọc |
| Changesets/SemVer release note | Tùy chọn | Versioning |
| Pre-commit hooks | Khuyến nghị | Run lint/secret scan trước commit |

## MCP/coding assistant hỗ trợ

| MCP/tool | Mức | Vai trò |
|---|---|---|
| Filesystem tool | Bắt buộc | Đọc/sửa file trong workspace |
| Git tool | Khuyến nghị | Xem diff/status/history |
| Shell tool | Bắt buộc | Chạy test/lint/script |
| PostgreSQL MCP | Khuyến nghị khi có DB | Inspect schema/query |
| Playwright MCP | Khuyến nghị khi làm Web | Test UI bằng browser automation |
| OpenAPI tooling | Khuyến nghị | Kiểm API contract/client |
| Docker/log tool | Khuyến nghị | Xem container/log |
| Grafana/Sentry MCP | Tùy chọn production | Debug lỗi vận hành |

Không cấp MCP quyền đọc secret production hoặc `.env` thật.

## Checklist cài đặt theo thứ tự

### Bước 1 - cài để bắt đầu code

- Git.
- IDE.
- Docker Desktop.
- Python 3.12+.
- Node.js Active LTS.
- pnpm hoặc npm.
- PostgreSQL client.
- FFmpeg.
- gitleaks.
- VS Code extensions/IDE plugins cho Python, TypeScript, Docker, Markdown.

### Bước 2 - khi scaffold backend/local stack

- PostgreSQL container.
- Redis container.
- RabbitMQ container.
- MinIO container.
- FastAPI stack.
- pytest/ruff/Alembic.
- OpenAPI docs.

### Bước 3 - khi làm Web/Mobile

- Next.js/React/TypeScript.
- Tailwind + UI component library.
- React Native/Expo hoặc React Native CLI.
- Android Studio.
- JDK tương thích.
- Mobile secure storage library.

### Bước 4 - khi làm AI/ANSVIS

- ANSVIS/AIBOX.
- ANSTS nếu cần custom/fine-tune cho pipeline đặc thù.
- NVIDIA driver/CUDA theo máy.
- VLC/ONVIF Device Manager.
- Tool kiểm RTSP/video sample.

### Bước 5 - bắt buộc trước staging/production

- Secret manager.
- Semgrep.
- pip-audit/npm audit.
- Trivy.
- OWASP ZAP baseline.
- Prometheus/Grafana.
- Log aggregation.
- Backup/restore tooling.
- Reverse proxy/TLS.

## Quyết định stack mặc định

| Hạng mục | Chọn mặc định |
|---|---|
| Backend | Python + FastAPI |
| Database chính | PostgreSQL |
| Cache/lock | Redis |
| Queue | RabbitMQ |
| Object storage | MinIO local, S3-compatible production |
| Web | Next.js + React + TypeScript |
| Mobile | React Native |
| AI integration | ANSVIS/AIBOX HTTP Trigger |
| AI training | Không mặc định; ANSTS chỉ dùng nếu cần custom/fine-tune, dữ liệu lấy từ camera dự án qua ANSVIS/AIBOX |
| Security scan | gitleaks + Semgrep + dependency audit + Trivy + ZAP |
| Observability | OpenTelemetry + Prometheus + Grafana + Loki/Sentry |

## Những thứ chưa nên mua/cài vội

- Kubernetes: chỉ cần khi Docker Compose/VM không còn đủ.
- ClickHouse/OpenSearch analytics: chỉ cần khi báo cáo/event quá lớn.
- Paid APM lớn: dùng Sentry/Grafana trước.
- Cloud GPU training: không dùng mặc định; chỉ xem xét nếu dữ liệu ANSVIS/camera đã được phê duyệt đưa ra ngoài, mã hóa, audit đầy đủ và không thể train local.
- MongoDB: không dùng làm core database; chỉ nghiên cứu nếu có use case phụ rõ.
