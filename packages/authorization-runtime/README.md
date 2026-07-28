# Camera AI authorization runtime

This package consumes the version-pinned authorization catalog and provides:

- a pure fail-closed decision point with no role-name matching;
- current tenant/school/object scope, purpose, consent, assignment, retention and legal-hold checks;
- composable SQLAlchemy predicates for row filtering before fetch;
- minimized denial and permission-change audit intents through `camera-ai-audit-producer`.

It owns no database, migration, credential, session, public route or cross-schema query. Owning
services load their own records, pass current protected attributes, apply the returned predicate to
their own repository query, and remain responsible for action-specific success audits.

Protected denial and missing-object responses are intentionally indistinguishable. Internal denial
reasons are stable codes for audit only. An unavailable audit recorder refuses the guarded operation;
an unavailable/missing policy version returns `AUTHZ_POLICY_UNAVAILABLE`.

Data handled by decisions is High and may gate Critical child, guardian, biometric and evidence
records. Tests use synthetic UUIDs only. No values are logged by this package.

Local verification:

```powershell
rtk .\.venv\Scripts\python.exe scripts/check_authorization_catalog.py
rtk .\.venv\Scripts\python.exe -m pytest packages/authorization-runtime/tests -q
```

Rollback is application-only: stop wiring the runtime and revert the package/catalog together. No
schema or stored data is created. Production activation requires the consuming service's deployment
and policy approvals.
