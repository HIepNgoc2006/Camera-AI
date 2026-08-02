# Web Portal

Minimal Next.js foundation for the AI Camera School Web Portal.

## Scope

- Public `/login` placeholder that does not collect credentials.
- Server-side guarded `/app` shell with a versioned, permission-aware,
  default-deny route policy.
- Public `/not-authorized` fallback.
- Reusable UI-action visibility checks that use the same validated permission
  snapshot as route decisions.
- One typed API Gateway client boundary under `src/shared/api/`.
- Fake/session-neutral tests only.
- Versioned `web_bff_session_policy_v1` contract, synthetic negative canaries,
  and strict server-snapshot mapping. Runtime session integration remains absent.

Real authentication, MFA, business dashboards, sensitive data, evidence media,
analytics, hosting and production deployment are intentionally out of scope.

## Runtime

- Node.js `24.17.0` from `.nvmrc`
- npm `11.13.0`
- Next.js `16.2.12`
- React `19.2.8`
- TypeScript `6.0.3`

Dependencies and their exact transitive versions are recorded in
`package-lock.json`. Installations must stay inside this package and use the
workspace npm cache:

```powershell
npm --cache "D:\WORKSAPCE\Camera AI\.local\cache\npm" ci
npm run dev
```

Do not use global installs or the user-level npm cache for project work.

## Environment

Copy `.env.example` to an ignored local environment file and replace the reserved
`.invalid` placeholder with the local API Gateway URL:

```text
NEXT_PUBLIC_API_GATEWAY_URL=https://api-gateway.example.invalid/
```

The API client rejects missing or malformed values, embedded credentials, query
parameters, fragments and non-loopback plain HTTP URLs. Error messages never echo
the configured value.

## Quality

```powershell
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
npm run quality
```

`npm run quality` is also called by the repository quality gate.

## Security notes

- `readSessionSnapshot` deliberately returns `null`, so protected routes remain
  closed until Issue #70 implements the approved server-only Identity/BFF
  integration for `web_bff_session_policy_v1`.
- The policy source is
  `packages/web-bff-session-policy/web-bff-session-policy-v1.json`; the
  code-coupled operator/developer runbook is
  `../../docs/security/web-bff-session-policy.md`.
- Access/refresh material remains server-only. The browser must not put tokens,
  MFA values, authorization state, or cookie values in localStorage,
  sessionStorage, readable cookies, URLs, HTML, analytics, logs, or client state.
- The route guard requires exact BFF and RBAC policy versions, strict
  actor/tenant/school/MFA fields, authoritative UTC expiry timestamps, and a
  non-expired session. Unknown fields and stale/malformed snapshots fail closed.
- Protected route groups are evaluated in server App Router layouts and remain
  dynamic. Public routes are explicit; unknown routes, policy versions,
  permissions and malformed snapshots fail closed.
- The `/app` layout guards the shared shell with the catalogued Web view
  permissions. Every future protected route group must also evaluate its exact
  route policy in a server layout before rendering feature content.
- Permission names come from
  `packages/authorization-policy/permission-catalog-v1.json`. Role-name matching
  is not an authorization mechanism.
- Redirect destinations and reason codes are internal allowlists. The guard
  never accepts or echoes a client-provided return URL.
- UI actions use `isUiActionVisible` and default to hidden, but route/UI guards
  do not replace backend object-level authorization, purpose/consent checks or
  audit.
- Feature code must use the typed API Gateway client; it must not call internal
  services, databases, queues or object storage directly.
- Do not persist access tokens or sensitive records in browser storage.
- Do not render untrusted HTML or add real people, face, camera or evidence data
  to fixtures.
