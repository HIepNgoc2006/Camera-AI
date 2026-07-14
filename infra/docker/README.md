# Local Docker stack

This stack is for local development and sanitized integration tests only. It is not a production topology or a backup solution.

## Services and pinned images

| Service | Image | Host access | Persistent path |
|---|---|---|---|
| PostgreSQL test | `postgres:17.10-bookworm` | `127.0.0.1:55432` by default | `./.local/docker-data/postgres-test/` |
| Redis | `redis:7.4.9-alpine` | `127.0.0.1:6379` | `./.local/docker-data/redis/` |
| RabbitMQ | `rabbitmq:4.3.2-management-alpine` | `127.0.0.1:5672`, management `127.0.0.1:15672` | `./.local/docker-data/rabbitmq/` |
| MinIO | `quay.io/minio/minio:RELEASE.2025-06-13T11-33-47Z` | API `127.0.0.1:9000`, console `127.0.0.1:9001` | `./.local/docker-data/minio/` |

Compose pins each image by exact version and digest. PostgreSQL is under the `test-db` profile because the native `Camera_AI` instance remains the default development database. The isolated container never binds host port `5432`.

## Configuration validation

Use placeholder values from the tracked example. Never copy production values into the workspace.

```powershell
rtk docker compose --env-file .env.example -f compose.yml config --quiet
```

## Start and verify

Start the default local dependencies:

```powershell
rtk docker compose --env-file .env.example -f compose.yml up -d redis rabbitmq minio
rtk docker compose --env-file .env.example -f compose.yml ps
```

Start the isolated PostgreSQL test database only when an integration test requires it:

```powershell
rtk docker compose --env-file .env.example -f compose.yml --profile test-db up -d
rtk docker compose --env-file .env.example -f compose.yml --profile test-db ps
```

Expected state is `healthy` for every started service. The stack uses an internal Docker network and publishes required ports on loopback only.

## Stop without deleting data

```powershell
rtk docker compose --env-file .env.example -f compose.yml --profile test-db down
```

`down` stops and removes containers/network but preserves the bind-mounted service data.

## Reset one service safely

Reset is destructive and is never part of normal shutdown.

1. Stop the affected service cleanly.
2. Resolve the target to an absolute path and verify it is exactly under `D:\WORKSAPCE\Camera AI\.local\docker-data\<service>\`.
3. Identify whether fake/sanitized data needs backup or migration.
4. Obtain explicit user approval naming the service and verified target.
5. Delete only that service directory, recreate it with the container's expected permissions, then start and verify the service.

Never reset native PostgreSQL data, the whole workspace, `.git`, user profile, Docker socket, credential store, or any directory outside `.local\docker-data\`.

## Security boundaries

- Only fake/sanitized development data is allowed in local bind mounts.
- Do not store real student/staff data, face images/embeddings, evidence, raw ANSVIS payloads, credentials, tokens, keys, licenses, dumps, backups, or real `.env` content.
- MinIO has no public bucket policy. Bucket creation and signed-URL behavior belong to later application/integration issues.
- Redis is reachable only on host loopback and the private Compose network; production authentication/network controls are defined separately.
- Secrets for staging/production must use an approved secret manager and managed/encrypted storage.
