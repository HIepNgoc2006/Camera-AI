# Web BFF session policy

`web-bff-session-policy-v1.json` is the sanitized, machine-readable baseline for Issue #162. It
defines the browser, Web BFF, API Gateway, and Identity Service trust boundaries; server-only token
custody; session-cookie, CSRF/origin, redirect, refresh, logout, expiry, and degradation behavior;
and the exact session states consumed by the Web login flow.

The baseline is inactive. It does not create a session, cookie, token, secret, endpoint, or runtime
configuration. Production activation remains blocked on Issue #70, an approved deployment profile,
an Identity-owned absolute/inactivity expiry snapshot contract, named Security/Ops review, and a
separate change/rollback record.

Run the deterministic checker from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/check_web_bff_session_policy.py
```

The checker also evaluates the synthetic canary matrix. It rejects browser token custody, readable
session cookies, cookie downgrade, missing CSRF/origin controls, unsafe redirects, token logging,
client-authored authorization state, invented timeout values, and fail-open session transitions.
