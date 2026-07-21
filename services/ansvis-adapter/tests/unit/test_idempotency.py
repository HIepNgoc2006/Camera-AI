from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from ansvis_adapter.application.ports import AuthenticatedSource
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import IdempotencyIdentityKind
from ansvis_adapter.domain.models import EventAttributes, HealthStatus
from ansvis_adapter.infrastructure.idempotency import (
    ContractIdempotencyDeriver,
    IdempotencyPolicy,
)
from ansvis_adapter.schemas.events import parse_and_normalize_event

FALLBACK_KEY = hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:idempotency-fallback-key").digest()


def event_payload() -> dict[str, object]:
    return {
        "schema_version": "ansvis_http_trigger_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": "event_test_ansvis_0001",
        "event_type": "camera.health.changed",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "event_time": "2030-01-01T00:00:00Z",
        "correlation_id": "corr_test_ansvis_0001",
        "attributes": {"status": "online"},
    }


def authenticated_source(
    *,
    tenant_ref: str = "tenant_test_0001",
    school_ref: str = "school_test_0001",
    source_namespace: str = "ansvis.test.source",
) -> AuthenticatedSource:
    return AuthenticatedSource(
        source_namespace=source_namespace,
        subject_ref="source_subject_test_0001",
        tenant_ref=tenant_ref,
        school_ref=school_ref,
    )


class FakeFallbackKeys:
    def __init__(self, value: bytes | None = FALLBACK_KEY, *, unavailable: bool = False) -> None:
        self.value = value
        self.unavailable = unavailable
        self.versions: list[str] = []

    def key_for(self, version: str) -> bytes | None:
        self.versions.append(version)
        if self.unavailable:
            raise RuntimeError("synthetic provider outage")
        return self.value


def deriver(keys: FakeFallbackKeys | None = None) -> ContractIdempotencyDeriver:
    return ContractIdempotencyDeriver(fallback_keys=keys or FakeFallbackKeys())


def compact_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def test_primary_vector_matches_the_approved_v1_projection_and_fingerprint() -> None:
    payload = event_payload()
    event = parse_and_normalize_event(payload)
    keys = FakeFallbackKeys(unavailable=True)

    descriptor = deriver(keys).derive(event, authenticated_source())

    primary_projection = {
        "tenant_ref": "tenant_test_0001",
        "source_namespace": "ansvis.test.source",
        "source_event_id": "event_test_ansvis_0001",
    }
    expected_key = "idem_source_v1_" + hashlib.sha256(compact_json(primary_projection)).hexdigest()
    canonical_event = {
        "schema_version": "ansvis_canonical_event_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": "event_test_ansvis_0001",
        "event_type": "camera.health.changed",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "occurred_at": "2030-01-01T00:00:00.000000Z",
        "attributes": {"status": "online"},
        "time_policy_version": "time_policy_v1",
        "idempotency_key": expected_key,
    }
    expected_fingerprint = "sha256:" + hashlib.sha256(compact_json(canonical_event)).hexdigest()

    assert descriptor.identity_kind is IdempotencyIdentityKind.SOURCE
    assert descriptor.idempotency_key == expected_key
    assert descriptor.canonical_fingerprint == expected_fingerprint
    assert keys.versions == []


def test_retry_correlation_is_excluded_but_changed_content_conflicts() -> None:
    first = parse_and_normalize_event(event_payload())
    retry_payload = event_payload()
    retry_payload["correlation_id"] = "corr_test_ansvis_retry_0001"
    retry = parse_and_normalize_event(retry_payload)
    changed = replace(
        retry,
        attributes=replace(retry.attributes, status=HealthStatus.OFFLINE),
    )
    policy = deriver()

    first_descriptor = policy.derive(first, authenticated_source())
    retry_descriptor = policy.derive(retry, authenticated_source())
    changed_descriptor = policy.derive(changed, authenticated_source())

    assert retry_descriptor == first_descriptor
    assert changed_descriptor.idempotency_key == first_descriptor.idempotency_key
    assert changed_descriptor.canonical_fingerprint != first_descriptor.canonical_fingerprint


def test_primary_identity_is_scoped_by_authenticated_tenant_and_source() -> None:
    event = parse_and_normalize_event(event_payload())
    other_tenant_event = replace(event, tenant_ref="tenant_test_other_0001")
    other_source_event = replace(event, source_namespace="ansvis.test.other")
    policy = deriver()

    baseline = policy.derive(event, authenticated_source())
    other_tenant = policy.derive(
        other_tenant_event, authenticated_source(tenant_ref="tenant_test_other_0001")
    )
    other_source = policy.derive(
        other_source_event, authenticated_source(source_namespace="ansvis.test.other")
    )

    assert (
        len({baseline.idempotency_key, other_tenant.idempotency_key, other_source.idempotency_key})
        == 3
    )


def test_fallback_vector_is_keyed_versioned_and_deterministic() -> None:
    payload = event_payload()
    payload["source_event_id"] = None
    payload["correlation_id"] = "corr_test_ansvis_fallback_0001"
    payload["attributes"] = {
        "status": "online",
        "track_id": "track_test_0001",
        "detection_key": "detection_test_0001",
    }
    event = parse_and_normalize_event(payload)
    keys = FakeFallbackKeys()

    descriptor = deriver(keys).derive(event, authenticated_source())

    fallback_projection = {
        "version": "ansvis_fallback_idempotency_v1",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "source_namespace": "ansvis.test.source",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "event_type": "camera.health.changed",
        "event_time_bucket": str(int(datetime(2030, 1, 1, tzinfo=UTC).timestamp())),
        "track_id": "track_test_0001",
        "detection_key": "detection_test_0001",
    }
    expected_key = (
        "idem_fallback_v1_"
        + hmac.digest(FALLBACK_KEY, compact_json(fallback_projection), "sha256").hex()
    )

    assert descriptor.identity_kind is IdempotencyIdentityKind.FALLBACK
    assert descriptor.idempotency_key == expected_key
    assert keys.versions == ["ansvis_fallback_idempotency_v1"]
    assert all(
        marker not in descriptor.idempotency_key
        for marker in ("tenant_test", "track_test", "detection_test")
    )


@pytest.mark.parametrize(
    "keys",
    [
        FakeFallbackKeys(None),
        FakeFallbackKeys(b"short"),
        FakeFallbackKeys(b"x" * 129),
        FakeFallbackKeys(unavailable=True),
    ],
)
def test_fallback_key_provider_failures_are_masked_and_fail_closed(
    keys: FakeFallbackKeys,
) -> None:
    payload = event_payload()
    payload["source_event_id"] = None
    payload["attributes"] = {
        "status": "online",
        "track_id": "track_test_0001",
        "detection_key": "detection_test_0001",
    }
    event = parse_and_normalize_event(payload)

    with pytest.raises(AnsvisAdapterError) as raised:
        deriver(keys).derive(event, authenticated_source())

    assert raised.value.code == "EVENT_DURABLE_RECEIPT_UNAVAILABLE"
    assert "synthetic provider outage" not in str(raised.value)


def test_missing_fallback_identity_and_source_mismatch_fail_before_derivation() -> None:
    event = parse_and_normalize_event(event_payload())
    missing = replace(
        event,
        source_event_id=None,
        attributes=EventAttributes(status=HealthStatus.ONLINE),
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_FALLBACK_IDENTITY_INSUFFICIENT"):
        deriver().derive(missing, authenticated_source())
    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_MAPPING_DENIED"):
        deriver().derive(event, authenticated_source(tenant_ref="tenant_test_other_0001"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"primary_version": "source_identity_v2"},
        {"fallback_version": "ansvis_fallback_idempotency_v2"},
        {"canonicalization_version": "camera_ai_canonical_json_v2"},
        {"time_policy_version": "time_policy_v2"},
        {"fallback_time_bucket_seconds": 2},
    ],
)
def test_policy_drift_requires_a_new_approved_version(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="approved V1 contract"):
        IdempotencyPolicy(**overrides)  # type: ignore[arg-type]
