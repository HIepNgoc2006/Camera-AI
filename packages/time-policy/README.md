# Time policy contract

`time-policy-v1.json` is the machine-readable baseline for event timestamp validation and clock
health. The owning runbook is
[`docs/operations/time-synchronization-policy.md`](../../docs/operations/time-synchronization-policy.md).

The contract contains stable policy metadata, UTC/IANA rules, clock-health thresholds, replay limits
and error codes. It contains no endpoint, hostname, IP address, credential, camera identifier or
environment-specific setting. A deployed environment must resolve its approved time sources and
school timezone configuration outside this package.

Published policy versions are immutable. Change a threshold or behavior by adding a new version,
running the compatibility fixtures and explicitly promoting that version. Do not edit an active
version in place.
