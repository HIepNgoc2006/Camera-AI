# Consent withdrawal and data disposition policy contract

`consent-withdrawal-policy-v1.json` is the machine-readable implementation baseline for consent
withdrawal, immediate deny-before-dispose, owner propagation, legal hold, independent lawful basis,
data disposition, reconciliation, restore reapplication, minimized completion evidence, and stable
fail-closed behavior.

This package authorizes policy and later implementation work; it does not create a migration, call
ANSVIS or another provider, delete or anonymize a record/object, activate a runtime workflow, or
invent a legal/retention decision. `runtime_activation.status` stays blocked until named
Privacy/Legal, Security/Ops, business-owner, and affected store-owner approvals plus a separate
authorized destructive change record exist.

An effective withdrawal denies new biometric processing, recognition/enrollment, subject-linked
notification, evidence access, and new report/export use before asynchronous disposal starts. A
legal hold pauses only the exact physical disposition in its approved scope. It never restores
consent, purpose, processing, decrypt, evidence, notification, or export authority.

The contract contains no real student, guardian, staff member, relationship, biometric reference,
face media, device token, credential, provider identifier, database row, backup content, object
locator, raw payload, or production identifier. Compatibility fixtures use synthetic opaque
references and controlled field names only.

Published versions are immutable. Any authority, maturity, state, transition, owner/store,
disposition, legal-hold/lawful-basis, completion-evidence, retry/reconciliation, restore, audit,
error, approval, or activation change requires a new version and explicit supersession evidence.

The human-readable authority is the “Consent withdrawal and data disposition policy” section in
`implementation-planning/planning/security-privacy-plan.md`. Encryption, audit, retention, legal
hold, backup/restore, and field-handling constraints remain governed by
`implementation-planning/planning/database-and-encryption-plan.md`.
