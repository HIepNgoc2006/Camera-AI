# Infrastructure

Chứa cấu hình Docker, deployment, networking, secret injection và observability gắn với implementation.

- Secret không nằm trong Compose, Dockerfile, image layer hoặc command line.
- Persistent Docker data local chỉ dùng `./.local/docker-data/<service>/` và fake/sanitized data.
- Không mount toàn workspace, user profile, Docker socket, credential store hoặc host root.
- Staging/production không dùng workspace-local storage path.

Root `compose.yml` đã khai báo stack local được pin digest gồm Redis, RabbitMQ và MinIO; PostgreSQL
test nằm trong profile `test-db` riêng để không đụng native PostgreSQL mặc định. Tất cả port chỉ bind
loopback và persistent bind mount nằm dưới `./.local/docker-data/<service>/`.

File cấu hình có sẵn không có nghĩa container đang chạy. Chỉ quản lý stack qua project Docker MCP;
không dùng raw `docker build`, `docker pull`, `docker run`, `docker create` hoặc state-creating
`docker compose`. Việc start/reset/prune/migrate dữ liệu cần issue và quyền riêng phù hợp.
