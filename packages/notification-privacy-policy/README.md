# Notification privacy policy contract

`notification-privacy-policy-v1.json` is the machine-readable implementation baseline for in-app,
push, and email notification privacy. It locks current-recipient/object authorization, generic
content allowlists, endpoint protection, retry/DLQ minimization, cancellation, expiry, fresh
notification-open authorization, audit redaction, and stable denial behavior.

This package authorizes implementation work for Issue #65; it does not activate a runtime policy,
dispatch a provider request, or create a recipient endpoint. `runtime_activation.status` stays
blocked until named Privacy/Legal, Security/Ops, and business-owner approvals are recorded outside
this contract. Services must fail closed while those approvals or an exact active version are
missing.

The contract contains no real recipient, student, guardian, staff member, device token, email
address, phone number, provider configuration, credential, endpoint, signed URL, object locator,
media, biometric value, raw ANSVIS payload, or production identifier. Compatibility fixtures use
synthetic opaque references and generic field names only.

Published versions are immutable. Any role, relationship, channel, content, permission, purpose,
consent, endpoint, retry/DLQ, expiry, cancellation, audit, error, provider boundary, or activation
change requires a new version, compatibility verification, approval record, and explicit
supersession.

The human-readable authority is the “Notification privacy policy” section in
`implementation-planning/planning/security-privacy-plan.md`; encryption, audit, endpoint, and
retention constraints remain governed by
`implementation-planning/planning/database-and-encryption-plan.md`.
