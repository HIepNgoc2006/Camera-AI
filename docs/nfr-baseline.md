# Sanitized NFR baseline

> Publication status: pilot design baseline; not a production SLA.
>
> Local source authority (not published in the implementation repository):
> `implementation-planning/planning/non-functional-requirements-plan.md`.
>
> Canonical body SHA-256: `2376e23958cebcd9b290d61c57b726fc7ade93730d422e456456f96899fb4219`
>
> Hash rule: SHA-256 of the UTF-8 text after the `baseline-body:start` marker, with line endings
> normalized to LF and exactly one trailing LF. The metadata above is excluded.

<!-- baseline-body:start -->

## Status and scope

This document publishes only the approved, sanitized non-functional values needed by implementation,
review, and test work. It contains no deployment topology, credentials, production identifiers,
personal data, biometric data, evidence, or raw ANSVIS payloads.

The values are planning baselines for a pilot. Production objectives require a Business Impact
Analysis (BIA), measured pilot evidence, dependency review, security approval, and an explicit
service-level decision.

## Load model and capacity

### Measured input

The source measurement supplied on 2026-07-16 was:

```text
2 cameras x 2 AI tasks
2,000 JSON events over 2 hours
```

The measurement used sanitized JSON metadata and is not evidence that every task, scene, rule, or
camera behaves identically.

### Derived planning baseline

Assuming linear scaling solely for preliminary capacity planning:

```text
measured aggregate rate = 2,000 / 7,200
                          = 0.278 events/second

rate per camera-task     = 2,000 / (2 x 2 x 7,200)
                          = 0.0694 events/second

maximum camera-tasks     = 34 cameras x 7 pipelines
                          = 238 camera-task pipelines

derived average rate     = 0.0694 x 238
                          = 16.53 events/second
```

If that average were sustained continuously, the database planning volume would be approximately
1.428 million event rows per day. Core business tables must use deliberate modeling, indexing,
partitioning, and retention; PostgreSQL must not store media binary or verbose raw payloads as the
primary business record.

At an illustrative average of 200 KiB of media for every event, storage would approach 286 GB/day
before overhead. This is a worst-case sizing illustration, not an approved media policy. Evidence
must be attached only where required and stored in private object storage under retention controls.

### Theoretical ceiling and guardrail

At a 10 FPS capture rate, configuring all 238 camera-task pipelines to emit on every detection could
produce a theoretical ceiling of:

```text
238 x 10 FPS = 2,380 events/second
```

This is not the normal load target. An `Every Detection` configuration at this scale must be blocked
unless it has explicit capacity, privacy, storage, and operational approval. Prefer an approved
combination of appearing/stable-duration rules, repeat interval, debounce or cooldown, ROI, and
schedule.

### Extrapolation limits

The 16.53 events/second value is an engineering baseline, not a forecast, because:

- the seven pipelines can have different models, rules, schedules, ROIs, and event frequencies;
- not every camera necessarily runs every pipeline;
- detection-per-frame settings can raise event volume by orders of magnitude;
- crowds, peak periods, and retry after network recovery can create correlated bursts;
- media upload and processing have different network, compute, and storage costs from JSON metadata;
- ANSVIS license, active-engine, decode, GPU/VRAM, model latency, frame age, and frame-drop capacity
  still require measured evidence.

After pilot measurement, staging capacity must use the greater of this baseline and the approved
pilot p99 rate multiplied by an approved headroom factor.

## Performance and load profiles

### Test profiles

All test traffic must use fake or sanitized JSON events without base64 media.

| Profile | Required load |
|---|---:|
| Contract smoke | 5 events/second for 15 minutes |
| Staging sustained | 50 events/second for 60 minutes |
| Staging burst | 200 events/second for 5 minutes |
| Soak | At least 35 events/second for 8 hours |
| Fault recovery | Controlled worker, broker, or network interruption followed by retry, duplicate, and backlog-drain verification |

For the soak profile, replace 35 events/second with the pilot p95 rate multiplied by an approved
safety factor of 2 when that result is higher.

JSON payloads should remain at or below 64 KiB. The approved contract defines the hard limit;
oversized requests must be rejected before business processing.

### Latency and recovery targets

The system provides near-real-time event processing, not hard real-time processing. Percentiles must
include slow requests and be reported with concurrency, fake dataset, payload size, cache state,
hardware, and error rate.

| Measurement | Pilot target |
|---|---:|
| Durable ingestion ACK | p95 <= 300 ms; p99 <= 1 s |
| Event readable through API/dashboard | p95 <= 5 s; p99 <= 15 s |
| Invalid or oversized payload rejection | p95 <= 200 ms before business processing |
| Backlog after staging burst | Drain <= 15 minutes with no accepted-event loss |

An event is accepted only after durable receipt. Data held only in process memory is not accepted.
The ingestion path is at-least-once and must use source-scoped idempotency; it does not claim
end-to-end exactly-once delivery.

## Availability and recovery

The provisional pilot availability objective for the control API and event-ingestion path is
99.5% per month, excluding announced maintenance windows. It must not be presented as a production
SLA or raised while unresolved single points of failure remain.

| Data or capability | Provisional RPO | Provisional RTO |
|---|---:|---:|
| Identity, permission, consent, and audit | <= 15 minutes | <= 4 hours |
| Event metadata, attendance, and violation records | <= 15 minutes | <= 4 hours |
| Evidence objects | <= 24 hours | <= 8 hours |
| Cache, dashboard aggregates, and derived data | Rebuildable | <= 4 hours |
| Approved configuration and model registry | <= 24 hours | <= 8 hours |

ANSVIS event storage is not the sole recovery source for business records. Evidence recovery requires
versioning or backup plus tested restoration. Cache is never a source of truth. Edge buffering and
replay behavior remain dependencies that must be proven before pilot.

## Verification and change control

Implementation evidence must record the active contract and configuration version, camera-task test
mapping, payload size, event rate, p50/p95/p99 latency, error and retry rate, queue depth and drain
time, storage growth, and relevant compute saturation. Camera or person identifiers in evidence must
be synthetic or opaque.

Any change to a published value requires:

1. approval in the local source authority;
2. an update to this sanitized document without copying local-only material;
3. regeneration and verification of the canonical body hash;
4. relevant quality, link, secret, and sanitization checks;
5. review of dependent Issue acceptance criteria and load-test evidence.
