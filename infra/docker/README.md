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

1. Invoke `docker_camera.docker_compose_validate` with `{}`. This validates the fixed project
   topology and security constraints without starting containers or resolving environment values
   into output.
2. Run the repository Compose-quality gate from the workspace root:

   ```powershell
   rtk .\.venv\Scripts\python.exe scripts/quality.py compose
   ```

## Start and verify

Ask for explicit approval before starting services. Start the default local dependencies by invoking
`docker_camera.docker_compose_up` with:

```json
{"services": ["redis", "rabbitmq", "minio"]}
```

Start the isolated PostgreSQL test database only when an approved integration test requires it. It
is not part of the default service set and must be requested explicitly through
`docker_camera.docker_compose_up`:

```json
{"services": ["postgres-test"]}
```

Inspect the project stack only through `docker_camera.docker_compose_status` with `{}`. Expected
state is `healthy` for every started service. The stack uses an internal network and publishes
required ports on loopback only.

## Stop without deleting data

Use `docker_camera.docker_compose_stop` with the exact services that were started. For the default
set, pass `{"services": ["redis", "rabbitmq", "minio"]}`. If the isolated database was started,
stop it separately with `{"services": ["postgres-test"]}`.

This safe stop operation does not delete containers, images, networks, volumes, or bind-mounted
data.

## Reset one service safely

Reset is destructive and is never part of normal shutdown.

1. Stop the affected service cleanly.
2. Resolve the target to an absolute path and verify it is exactly under `D:\WORKSAPCE\Camera AI\.local\docker-data\<service>\`.
3. Identify whether fake/sanitized data needs backup or migration.
4. Obtain explicit user approval naming the service and verified target.
5. Perform only the separately reviewed reset procedure for that exact service, then restart it
   through `docker_camera.docker_compose_up` and verify it through
   `docker_camera.docker_compose_status`.

Never reset native PostgreSQL data, the whole workspace, `.git`, user profile, Docker socket, credential store, or any directory outside `.local\docker-data\`.

## Security boundaries

- Only fake/sanitized development data is allowed in local bind mounts.
- Do not store real student/staff data, face images/embeddings, evidence, raw ANSVIS payloads, credentials, tokens, keys, licenses, dumps, backups, or real `.env` content.
- MinIO has no public bucket policy. Bucket creation and signed-URL behavior belong to later application/integration issues.
- Redis is reachable only on host loopback and the private Compose network; production authentication/network controls are defined separately.
- Secrets for staging/production must use an approved secret manager and managed/encrypted storage.
