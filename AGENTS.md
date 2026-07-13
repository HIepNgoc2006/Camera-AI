# AGENTS.md - AI Camera School System

@C:\Users\hiep\.codex\RTK.md

## Mission

You are working on a school AI Camera system. Treat this as a high-sensitivity system because it may process children’s personal data, face images, biometric identifiers, attendance records, staff timekeeping, camera events, and security evidence.

Your job is not only to make code work. Your job is to make code correct, secure, maintainable, auditable, and understandable by another developer.

## Read first

Before coding or changing architecture, read these files:

1. `README.md`
2. `implementation-planning/planning/planning-index.md`
3. `implementation-planning/planning/system-master-plan.md`
4. `implementation-planning/planning/workstream-implementation-plan.md`
5. `implementation-planning/planning/architecture-stack.md`
6. `implementation-planning/planning/tooling-requirements.md`
7. `implementation-planning/planning/security-privacy-plan.md`
8. `implementation-planning/planning/database-and-encryption-plan.md`
9. `implementation-planning/planning/ai-ansvis-plan.md`
10. `implementation-planning/planning/ansvis-model-capability-matrix.md`
11. `implementation-planning/planning/coding-agent-rules.md`
12. `implementation-planning/planning/agent-scope-control-rules.md`
13. `implementation-planning/planning/delivery-quality-plan.md`
14. `implementation-planning/planning/operations-tracking-plan.md`
15. `implementation-planning/planning/risk-assessment.md`

If your task touches customer-facing requirements, also read:

- `project-docs/docs-du-an-ai-camera/docs-index.md`
- relevant docs under `project-docs/docs-du-an-ai-camera/`

If your task touches ANSVIS/AIBOX/AI:

- `references/Tong-hop-video-TAP-HUAN-CAMERA-AIBOX.md`
- `implementation-planning/planning/ai-ansvis-plan.md`
- `implementation-planning/planning/ansvis-model-capability-matrix.md`

## Scope boundaries

The software team scope includes:

- Backend/API.
- AI integration.
- ANSVIS/AIBOX event integration.
- Web Portal.
- Mobile App.
- Database.
- Security.
- Monitoring/logging.
- Deployment scripts/config.
- Documentation/runbook.

The software team scope does not include:

- Physical camera purchase.
- On-site survey.
- Cable installation.
- Physical network wiring.
- Mounting camera hardware.

Do not add hardware installation tasks unless the user explicitly asks.

## Planning and issue scope control

When working on planning, docs, tasks, or GitHub Issues, read `implementation-planning/planning/agent-scope-control-rules.md`.

Do not add new docs or issues just because a possible task can be imagined. Add them only when there is a real gap between customer requirements, project docs, implementation planning, security/privacy gates, or GitHub Issues.

Keep these layers separate:

- Executive summary: short view for boss/customer.
- Project docs: requirements, flows, architecture, acceptance.
- Implementation planning: technical rules, task planning, security gates.
- GitHub Issues: trackable work items.

If issues become numerous, use labels, milestones, project views, and executive summaries. Do not delete or merge issues casually just to make the count look smaller.

Before adding a GitHub Issue, check whether an existing issue already covers it. Every new issue must have a clear prefix, milestone, labels, acceptance criteria, and security/privacy impact when relevant.

## Non-negotiable security rules

Never:

- Read, print, paste, summarize, or expose real `.env` values.
- Commit `.env`, private keys, license keys, service account JSON, database dump, face DB export, or real camera credentials.
- Hard-code passwords, tokens, API keys, RTSP credentials, JWT secrets, S3 secrets, ANSVIS credentials, or license keys.
- Log face images, face embeddings, base64 images, access tokens, refresh tokens, passwords, RTSP URLs with credentials, or full raw ANSVIS payloads containing media.
- Use real student/parent/staff data in tests, fixtures, seed data, screenshots, public docs, or demo payloads.
- Store image/video binary directly in PostgreSQL tables.
- Make object storage buckets public.
- Let Web/Mobile call internal services directly while bypassing API Gateway.
- Let a service read another service’s database schema directly.
- Treat ANSVIS Event Storage as the only source of truth for business records.
- Enable ANSVIS debug mode in production.

Always:

- Use `.env.example` with placeholder values.
- Use a secret manager for staging/production secrets.
- Use private object storage plus short-lived signed URLs for evidence media.
- Add audit log for sensitive actions.
- Enforce object-level authorization for student/event data.
- Validate and normalize ANSVIS payloads before business processing.
- Use idempotency for event ingestion.
- Mask sensitive log fields.
- Add tests for auth, permission, and data boundaries.

## Data classification

Classify data before coding:

| Data | Sensitivity | Required handling |
|---|---:|---|
| Face image/crop/embedding/face DB | Critical | Consent, encryption, restricted access, audit, retention |
| Student/parent profile | Critical | RBAC/ABAC, object-level auth, no real test data |
| Attendance/timekeeping | High | Audit, permission, retention |
| Violation evidence image/video | High | Private storage, signed URL, export audit |
| ANSVIS event JSON | High | Schema validation, masking, retention |
| Logs/traces/errors | Medium/High | Redaction, retention, restricted access |
| Secret/config/license | Critical | Secret manager, no Git, rotation |

If unsure, classify as higher sensitivity.

## Required thinking process

Before implementing any task:

1. Identify the exact user requirement.
2. Identify the affected service/module.
3. Identify affected data classes.
4. Identify security/privacy impact.
5. Check existing docs/plans.
6. Check existing patterns in the repo.
7. Define the smallest safe change.
8. Define tests and verification commands.
9. Implement.
10. Verify.
11. Update docs/runbook if behavior or config changed.

Do not code first and reason later.

## Workstream separation rules

Before implementing or planning work, classify the task into one of these workstreams:

- Product Platform: Backend, database, Web Portal, Mobile App, auth, report, notification.
- ANSVIS Integration: Adapter, HTTP Trigger payload, camera/task registry, event ingestion, health dashboard.
- AI Model/Pipeline: Facial Recognition config, Littering Detection, Smoking Detection, Student Uniform Detection, Kitchen PPE Detection, custom training/fine-tune if required.
- QA/Security/Ops: tests, UAT, monitoring, backup, incident response, security scan.

Do not mix AI training work into Web/Mobile/Backend issues. Product Platform must be buildable with mock/sanitized ANSVIS events before real camera/model output is available.

Do not mix Web/Mobile UI work into AI model/pipeline issues unless explicitly required.

## Architecture rules

Use microservices-ready monorepo structure:

```text
apps/
services/
workers/
packages/
infra/
docs/
scripts/
```

Backend services should follow:

```text
service-name/
  README.md
  .env.example
  pyproject.toml
  alembic/
  src/
    service_name/
      main.py
      api/
      application/
      domain/
      infrastructure/
      schemas/
      config.py
      logging.py
  tests/
    unit/
    integration/
    contract/
```

Layer rules:

- `domain` contains pure business rules and must not import FastAPI, SQLAlchemy, RabbitMQ, S3, ANSVIS clients, or framework code.
- `application` coordinates use cases and transaction boundaries.
- `infrastructure` implements database, queue, storage, HTTP clients, ANSVIS adapters.
- `api` contains routes, dependency injection, request validation, auth guard.
- `schemas` contains request/response/event DTOs.

## Design patterns

Use these patterns when appropriate:

- Clean/Hexagonal Architecture for service boundaries.
- Repository Pattern for database access.
- Application Service for use cases.
- Adapter Pattern for ANSVIS, storage, notification, external APIs.
- DTO/Schema Pattern for API/event contracts.
- Outbox Pattern for reliable event publishing.
- Idempotency Pattern for ANSVIS events and notification dispatch.
- Policy Pattern for RBAC/ABAC/consent.
- Strategy Pattern for notification channels and event mapping.
- CQRS-lite for dashboards/reports.
- Feature Flag for AI shadow mode and staged rollout.

Do not over-engineer. Use patterns to clarify boundaries, not to add ceremony.

## Database rules

Default primary database: PostgreSQL.

Do not use MongoDB as the main transactional database for:

- students;
- parents;
- teachers;
- classes;
- attendance;
- permissions;
- audit;
- consent;
- violation records.

Use PostgreSQL schemas by service/domain:

- `identity`
- `school`
- `privacy`
- `camera`
- `integration`
- `events`
- `attendance`
- `timekeeping`
- `violation`
- `notification`
- `reporting`
- `evidence`
- `ai_registry`
- `audit`

Database rules:

- All schema changes require migration.
- Before creating or changing tables, read `implementation-planning/planning/database-and-encryption-plan.md`.
- Classify sensitive fields before migration: PII, biometric, evidence, event payload, secret metadata, audit data.
- Define encryption, retention, audit behavior, and object-level authorization before implementing repository/query code.
- Do not manually patch production schema.
- Do not concatenate raw SQL from user input.
- Do not store media binary in business tables.
- Use JSONB only for controlled payload flexibility, not as an excuse to avoid modeling core business data.
- Large event tables should be designed with retention/partitioning in mind.

## ANSVIS/AI rules

ANSVIS/AIBOX is treated as an external AI/video analytics platform.

Rules:

- Backend receives ANSVIS events through HTTP Trigger or approved integration only.
- Validate source, auth token/HMAC, payload schema, size, and event type.
- Normalize ANSVIS payload into internal event models.
- Do not spread raw ANSVIS field access across business services.
- Use idempotency key for every event.
- Prefer custom minimal HTTP Trigger payload.
- Prefer private media URL/signed URL over base64 media.
- Disable debug mode after testing.
- Append video only for event types that truly require evidence.
- Track ANSVIS task config, ROI, threshold, model, schedule, and version.

AI training/data rules:

- Facial Recognition for student attendance and staff timekeeping can start from ANSVIS built-in Face Detection/Facial Recognition.
- Littering Detection, Smoking Detection, Student Uniform Detection, and Kitchen PPE Detection must be treated as custom pipelines/model-rule combinations unless proven covered by available ANSVIS models.
- Custom training/fine-tune is not required for every function, but it may be required for the four custom pipelines if built-in/prebuilt models do not meet acceptance metrics.
- Training/fine-tune/evaluation data must come from project cameras through ANSVIS/AIBOX unless there is a separately approved exception.
- No real dataset in Git.
- No face image/crop in fixtures.
- Dataset must have manifest, checksum, source, consent status, label list, retention.
- Do not use external/Internet/other-school datasets for training, benchmark, or demo without approval, consent basis, and equivalent security controls.
- Model artifact must have version, metric, dataset hash, reviewer, approval status.
- Model must pass shadow mode before production.
- Sensitive AI decisions require human review if confidence is low or impact is high.

## Consent rules

If functionality uses biometric data:

- Check consent before processing.
- Check consent before storing.
- Check consent before showing/exporting.
- Support withdrawal/deactivation path.
- Audit all consent changes.

If consent is missing or unclear, block biometric processing by default.

## API rules

Every API must have:

- Clear route name.
- Request/response schema.
- Auth requirement.
- Permission rule.
- Error response shape.
- Audit behavior if sensitive.
- Tests for allowed and denied access.

Error response shape:

```json
{
  "error_code": "STABLE_ERROR_CODE",
  "message": "Human-readable message",
  "request_id": "req_..."
}
```

Never return stack traces, secret values, password hashes, token hashes, or internal credential references to clients.

## Web/Mobile rules

Web/Mobile must:

- Use API client layer, not random direct fetch calls inside components.
- Enforce route/screen guard by role.
- Hide unauthorized UI actions.
- Still rely on backend authorization as final enforcement.
- Avoid storing sensitive data in local unencrypted storage.
- Use secure storage for mobile tokens.
- Avoid rendering untrusted HTML.
- Avoid showing evidence image/video unless the user has permission.

Frontend structure should group by feature:

```text
features/
  attendance/
    api/
    components/
    hooks/
    screens-or-pages/
    types.ts
```

## Logging rules

Required log fields:

- `request_id`
- `service_name`
- `environment`
- `actor_id` if authenticated
- `event_id` or `correlation_id` for AI events
- stable error code

Forbidden log fields:

- password;
- token;
- API key;
- private key;
- RTSP credential;
- full RTSP URL with auth;
- face embedding;
- image base64;
- raw biometric payload;
- full `.env`;
- real student data in debug logs.

## Testing rules

Add tests based on risk:

| Change | Required tests |
|---|---|
| Auth/permission | Allowed + denied access tests |
| Student/event data | Object-level authorization tests |
| ANSVIS payload | Contract tests with sanitized fixtures |
| Event ingestion | Idempotency, retry, invalid payload |
| Attendance/violation | Business rule tests |
| Notification | Correct recipient, no sensitive media in push |
| Export/report | Permission + audit test |
| Database migration | Migration apply test |
| Security-sensitive code | Secret/log masking tests when applicable |

Use fake data only.

## Verification before completion

Before saying a task is complete, run relevant verification.

Possible commands:

- list files changed;
- run unit tests;
- run integration tests;
- run lint/typecheck;
- run secret scan;
- check local links in docs;
- check no unfinished placeholder markers if producing final docs;
- inspect generated OpenAPI if API changed.

Report exact verification performed. If verification cannot be run, say why and state the risk.

## Documentation rules

Update documentation when changing:

- architecture;
- service boundary;
- API contract;
- database schema;
- environment variables;
- security behavior;
- AI/ANSVIS integration;
- deployment/runbook;
- operational workflow.

Each service must have a README covering:

- purpose;
- API;
- events consumed/published;
- database schema;
- env vars;
- local run;
- tests;
- logs/metrics;
- security notes.

## File editing rules

- Preserve existing user work.
- Do not delete or move files unless the task requires it.
- Prefer small, focused changes.
- Do not create many scattered docs when one maintained doc is enough.
- Keep root clean: only project-level files such as `README.md`, `AGENTS.md`, config files, and future codebase root files.

## Escalation rules

Stop and ask the user when:

- A choice changes architecture materially.
- A task requires real credentials/secrets.
- A task requires deleting user data.
- A task requires using real student/face data.
- A task requires production access.
- A requirement conflicts with security/privacy rules.

If blocked, explain the blocker and propose safe alternatives.
