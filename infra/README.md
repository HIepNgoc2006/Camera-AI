# Infrastructure

Chứa cấu hình Docker, deployment, networking, secret injection và observability gắn với implementation.

- Secret không nằm trong Compose, Dockerfile, image layer hoặc command line.
- Persistent Docker data local chỉ dùng `./.local/docker-data/<service>/` và fake/sanitized data.
- Không mount toàn workspace, user profile, Docker socket, credential store hoặc host root.
- Staging/production không dùng workspace-local storage path.

Docker stack sẽ được triển khai trong issue riêng; scaffold này chưa khởi động container.
