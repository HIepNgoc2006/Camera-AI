# Web Portal

Minimal Next.js foundation for the AI Camera School Web Portal.

## Scope

- Public `/login` placeholder that does not collect credentials.
- Server-side guarded `/app` shell that defaults to denied.
- Public `/not-authorized` fallback.
- One typed API Gateway client boundary under `src/shared/api/`.
- Fake/session-neutral tests only.

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
  closed until the approved Identity integration replaces that seam.
- Route/UI guards do not replace backend object-level authorization.
- Feature code must use the typed API Gateway client; it must not call internal
  services, databases, queues or object storage directly.
- Do not persist access tokens or sensitive records in browser storage.
- Do not render untrusted HTML or add real people, face, camera or evidence data
  to fixtures.
