# Evidence access policy contract

`evidence-access-policy-v1.json` is the machine-readable implementation baseline for metadata,
thumbnail, original, download, and export authorization. It locks default-deny role/object scope,
consent/purpose/retention gates, legal-hold behavior, signed GET TTL boundaries, export controls,
audit minimization, stable reason codes, and public existence concealment.

This package authorizes implementation work for Issue #67; it does not activate a runtime policy.
`runtime_activation.status` remains blocked until named Privacy/Legal, Security/Ops, and business-owner
approvals are recorded outside this contract. Services must fail closed while those approvals or an
exact active policy version are missing.

The contract contains no endpoint, bucket, object locator, signed URL, credential, media, biometric
data, raw ANSVIS payload, personal profile, or environment-specific value. Fixtures use synthetic
opaque references only.

Published versions are immutable. Any permission, role, purpose, TTL, export, audit, error, or
activation change requires a new file/version, compatibility verification, approval record, and
explicit supersession. Never edit an active version in place.

The human-readable authority is the “Evidence access and signed URL policy” section in
`implementation-planning/planning/security-privacy-plan.md`; database/object-storage constraints
remain governed by `implementation-planning/planning/database-and-encryption-plan.md`.
