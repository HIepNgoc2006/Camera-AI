# AI Camera School Platform

Security-first software platform for school attendance, staff timekeeping, AI camera events, Web Portal, reporting, audit, and ANSVIS/AIBOX integration.

## Monorepo boundaries

This repository is microservices-ready without requiring every logical domain to run as a separate deployable service from day one.

| Path | Ownership |
|---|---|
| [`apps/`](apps/) | Approved user-facing applications, starting with the Web Portal |
| [`services/`](services/) | API Gateway and domain backend services |
| [`workers/`](workers/) | Queue consumers, scheduled jobs, and asynchronous processing |
| [`packages/`](packages/) | Versioned contracts and stateless shared libraries |
| [`infra/`](infra/) | Docker, deployment, networking, and observability configuration |
| [`docs/`](docs/) | Code-coupled API documentation, ADRs, and runbooks |
| [`scripts/`](scripts/) | Reviewable build, test, migration, deployment, and operations scripts |

## Dependency rules

- Web and Mobile access the platform through the API Gateway, never by calling internal services directly.
- Each backend service owns its domain and PostgreSQL schema. Cross-service access uses APIs, events, or versioned contracts; services do not read another service's schema.
- Shared packages contain no runtime secrets, environment-specific configuration, or business state.
- Repository data is placeholder, fake, or sanitized only. Real personal data, biometric data, evidence, credentials, raw ANSVIS payloads, datasets, and camera media are forbidden.
- Runtime topology is decided by implementation issues. These ownership boundaries do not force every logical module into a separate container.

## Current state

This milestone establishes repository ownership boundaries only. It does not yet add business logic, biometric processing, real ANSVIS integration, production infrastructure, or deployable services.
