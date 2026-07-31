# Abuse protection policy

`abuse-protection-policy-v1.json` is the sanitized, machine-readable baseline for Issue #44. It
defines the public surfaces, responsibility boundaries, abuse cases, inherited numeric limits,
safe-degradation invariants, monitoring evidence, and existing Issue ownership for DDoS, replay,
flood, and application abuse controls.

The document is an inactive implementation baseline. It is not a production WAF, CDN, firewall,
object-storage, or provider configuration and deliberately contains no provider identifiers,
network topology, credentials, tenant values, camera identifiers, or real traffic evidence.

## Authority and drift

Numeric controls are inherited from the API, ANSVIS, evidence-access, queue, identity, gateway, and
report baselines. Run the checker after changing any of those sources:

```powershell
.\.venv\Scripts\python.exe scripts/check_abuse_protection_policy.py
```

The checker fails if a required surface or responsibility disappears, a referenced metric is not
registered, a mitigation lacks an existing Issue owner, unsafe evidence fields are introduced, or
copied numeric limits drift from their authority.

Production activation remains blocked until sanitized load/abuse evidence, Web/client review,
provider-edge and operations approval, capacity evidence, and a production change/rollback record
exist. Rate limiting never substitutes for authentication, object authorization, consent,
retention, audit, private evidence delivery, or queue recovery.
