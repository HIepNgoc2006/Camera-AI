# DDoS, replay, flood, and abuse threat model

Status: sanitized implementation baseline; production activation inactive

Policy: `abuse_protection_policy_v1`

Scope: Issue #44; Product Platform, ANSVIS Integration, and QA/Security/Ops

## Decision and limits

This baseline separates application abuse from provider/infrastructure DDoS protection. It applies
to the public Web edge, Web/Mobile API, login, ANSVIS webhook, report/export, signed evidence access,
and private object delivery. It contains no live endpoint, provider account, origin address,
credential, tenant, camera, object key, traffic capture, or production capacity value.

The machine-readable authority is
`packages/abuse-protection-policy/abuse-protection-policy-v1.json`. Its copied thresholds are checked
against the existing API, ANSVIS, identity, evidence, report, and queue authorities. This document
does not activate a WAF/CDN/firewall, change production, or promise that an application rate limiter
can absorb volumetric DDoS.

All affected data is classified at least Medium. ANSVIS payload, attendance/timekeeping, violation,
report, and evidence access are High; credentials, protected topology, biometric-linked evidence,
and object locators are Critical. Missing or ambiguous security state denies sensitive work.

## Trust boundaries and ownership

| Boundary | Owns | Must never replace |
|---|---|---|
| Provider edge/CDN/WAF/DDoS service | Volumetric L3/L4/L7 absorption, managed WAF rules, connection/bandwidth shielding, safe static caching, origin concealment | AuthN/AuthZ, consent, audit, replay/idempotency |
| API Gateway | Sole public API entry, TLS policy, method/content/body bounds, route bucket, `Retry-After`, stable errors/request ID | Service object authorization or direct evidence delivery |
| Application services | Login throttling, actor/resource quota, object scope, consent/retention, replay/idempotency, sensitive audit | Provider DDoS capacity or public storage |
| Queue/workers | Bounded backlog/retry, circuit breaker, DLQ, drain/recovery observability | Front-door flood defense or unbounded buffering |
| Private object storage | Private policy, bounded GET, lifecycle defense-in-depth, provider request/egress visibility | Business authorization, public listing, permanent URL, client direct write |
| Security/Operations | Aggregate alerting, provider escalation, rule-change approval, rollback/post-incident review | Raw payload capture or publishing credentials/topology |

API Gateway remains the only public API entry. Internal services, PostgreSQL, Redis, RabbitMQ, and
object storage remain private even during an incident. Provider edge controls must restrict origin
access; otherwise an attacker can bypass the edge and its WAF/rate controls.

## Surface controls

### Public Web and Web/Mobile API

- Cache only safe public static assets. Never cache authenticated API responses, signed URLs, or
  evidence. API traffic still enters through Gateway.
- Gateway enforces the route bucket declared by the API contract. Current sustained/burst pairs are:
  login `5/10`, standard read `20/60`, sensitive write `5/15`, signed access `10/30`, export `1/3`,
  destructive `1/3`, admin read `10/20`, admin write `2/5`, report read `5/15`, audit read `5/10`,
  operations read `10/30`, and ANSVIS ingestion `50/200`.
- The key combines the authenticated actor or verified trusted source with the bounded route bucket.
  Provider-derived source reputation may add protection but never replaces actor/object checks.
- Excess work returns the stable `429` contract with `Retry-After`. A limiter dependency failure
  fails closed on login, sensitive, evidence, export, and ingestion paths rather than bypassing the
  control.
- Pagination, filter allowlists, request body limits, operation permissions, and idempotency for
  mutations prevent small requests from amplifying into unbounded database or worker work.

### Authentication

- Gateway rejects auth bodies over 8 KiB. The edge login bucket is `5 rps / 10 burst`.
- Identity additionally counts failed attempts per digested account (`5`) and digested source
  (`20`) in a 300-second window. Raw account/source values are not retained in limiter keys.
- A success clears only the account counter; it does not erase source pressure. Redis loss produces
  the stable fail-closed `503` outcome and never disables throttling.
- Responses do not disclose whether the account exists. Provider bot/challenge rules require a
  separate accessibility and client compatibility review before activation.

### ANSVIS webhook

- Accept only the approved HTTPS `POST` JSON contract. Reject over 64 KiB before parsing, enforce
  verified source identity, and limit each source namespace to `50 rps / 200 burst`.
- A 300-second replay window, 30-second future tolerance, source nonce/idempotency, canonical
  fingerprint, and durable receipt precede acknowledgement. Identical duplicates are bounded and
  harmless; conflicts reject without a second business effect.
- Clock or limiter dependency loss fails closed. Front-door limits remain enabled when the queue or
  database is degraded. The queue is never used as an unlimited flood absorber.

### Report/export

- Export uses the `1 rps / 3 burst` edge bucket, at most two concurrent exports per actor, and a
  bounded queue of 5,000 jobs. It remains asynchronous.
- At quota/queue capacity, deny new work with the stable rate/quota outcome while preserving already
  accepted jobs. Never fall back to synchronous generation.
- Export artifacts expire after seven days; delivery uses a 60-second signed GET. Source
  authorization is rechecked at delivery and ordinary viewing never implies export permission.

### Signed evidence and object delivery

- Signed-access minting uses `10 rps / 30 burst`. Standard signed GET defaults to 60 seconds and
  never exceeds 300; export delivery never exceeds 120 seconds.
- Object authorization, purpose, consent where applicable, retention/hold state, action permission,
  and access audit are mandatory before a URL is issued. Responses are `private, no-store`.
- Buckets are private, listing/direct client write are disabled, and no overload path creates a
  public bucket, permanent URL, raw object key, or origin bypass.
- Provider request, egress, and concurrency thresholds are environment-owned activation values.
  They are named and approved in the protected production change record, not copied into Git.

### Queue and retry pressure

- Warning begins at depth 5,000 for 300 seconds. Critical is depth 20,000 or drain ETA 900 seconds.
  A downstream error ratio above 10% over 60 seconds can open the bounded circuit.
- On pressure: keep front-door limits active, stop or slow claims, preserve durable accepted work,
  use bounded retry/jitter, quarantine terminal failures in DLQ, and resume through controlled
  half-open recovery. No automated destructive queue reset is part of this response.

## Abuse cases and safe degradation

| ID | Abuse case | Detection/control | Safe degradation |
|---|---|---|---|
| ABUSE-001 | Volumetric Web/API DDoS | Provider edge + origin restriction + Gateway buckets | Cache safe public assets; shed API load; never expose origin |
| ABUSE-002 | Credential stuffing/password spray | Edge login bucket + account/source failure limits | Stable `429`; limiter loss is non-enumerating `503` |
| ABUSE-003 | Expensive API/query amplification | Route bucket + pagination/filter/body bounds + quotas | Reject before database/queue amplification |
| ABUSE-004 | ANSVIS replay/duplicate flood | Source rate, nonce/window, idempotency/fingerprint | Bounded duplicate/conflict response; one business effect |
| ABUSE-005 | Malformed/oversized payload flood | Edge/Gateway content and size checks | Reject before deserialization/downstream calls |
| ABUSE-006 | Export generation amplification | Actor concurrency + edge bucket + bounded async queue | Deny new jobs; preserve accepted jobs; no sync fallback |
| ABUSE-007 | Signed URL mint/reuse abuse | Object auth + quota + short TTL + no-store + audit | Deny new grant; never relax consent/retention/audit |
| ABUSE-008 | Object egress exhaustion | Private storage + provider request/egress/concurrency profile | Throttle/deny delivery; no public or permanent fallback |
| ABUSE-009 | Queue/retry storm | Backpressure, bounded retry, circuit, DLQ | Stop claims and recover without silent loss |
| ABUSE-010 | Distributed low-and-slow abuse | Provider + route + actor/resource aggregate signals | Apply layered controls without raw identifier logs |

These invariants hold in every degradation mode:

- Gateway remains the only public API entry; internal origins and stores remain private.
- Authentication, authorization, object scope, consent, retention, and audit are never bypassed.
- Accepted events/exports are not silently discarded, and queue pressure never disables front-door
  limits.
- Evidence never falls back to public/permanent delivery.
- Errors and evidence never expose secrets, protected topology, payloads, media, or personal data.

## Monitoring and safe evidence

Use registered aggregate metrics for ANSVIS ingestion/rejections/ACK, outbox backlog/drain,
report export/queue/drain, and evidence access. Provider-edge, origin-pressure, generic API/login
throttle, and object-egress signals remain bounded signal codes until their runtime metric/alert is
implemented and registered by the owning issue.

Allowed evidence is limited to policy/deployment version, surface/route-bucket/outcome/reason/status
codes, aggregate count/rate/latency, fixed review window, and trusted request/correlation IDs. Review
one-minute, five-minute, and one-hour windows to distinguish bursts, sustained abuse, and recovery.

Never capture or attach access/refresh tokens, API keys, cookies, signed/credentialed URLs, raw source
addresses or user identifiers, student/staff/camera/provider identifiers, bucket/object keys,
provider topology, raw request/ANSVIS payload, image/video, face data, or real tenant traffic.
Screenshots and incident evidence must use only sanitized aggregate output.

## Activation, test, and rollback gates

This baseline is inactive. Activation requires all of the following:

1. Issue #46 supplies sanitized abuse, load, burst, dependency-loss, and recovery evidence.
2. Issue #78 reviews Web/client behavior, headers, caching, retry handling, and route compatibility.
3. Issue #95 supplies sustained capacity/backpressure evidence for the approved profile.
4. Issue #89 records the named provider profile, origin restriction test, Security/Ops approval,
   alert routes, on-call escalation, production change window, and rollback.
5. The change record confirms no auth/authz/consent/audit/private-evidence bypass and contains no
   provider secret or protected topology.

Rollback disables the new edge rule/profile or returns to the last approved version. It does not
make origins public, disable application controls, clear queues, delete evidence, or expose raw
traffic. Incident-driven emergency rules still require an owner, bounded duration, reason, audit,
and post-incident review.

## Existing implementation ownership

- #45: completed ANSVIS webhook auth/body/rate/replay/idempotency hardening.
- #35 and #96: completed queue/backpressure and deployment-capacity baselines.
- #67 and #137: completed private evidence boundary and identity throttling runtime.
- #46, #78, #89, and #95: test, client, provider/production, and sustained-capacity activation gates.
- #112: dependency/container/SAST/DAST scanning; complementary to, not a replacement for, abuse
  controls.

Review record: Backend, ANSVIS, Security, Operations, and Web/Mobile client concerns are represented
in this baseline. Current review is a single-developer sanitized baseline review. Cross-role review
is still required at activation; no production readiness is claimed.
