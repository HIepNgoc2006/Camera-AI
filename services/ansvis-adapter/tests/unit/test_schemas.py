from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC

import pytest
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.models import (
    EmotionInsightEvent,
    FaceObservationEvent,
    HealthStatusEvent,
    SuspectedViolationEvent,
)
from ansvis_adapter.schemas.events import (
    MAX_JSON_ARRAY_ITEMS,
    MAX_JSON_NESTING_DEPTH,
    inspect_json_envelope,
    load_json_object,
    parse_and_normalize_event,
)


def event_payload(event_type: str = "camera.health.changed") -> dict[str, object]:
    return {
        "schema_version": "ansvis_http_trigger_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": 10001,
        "event_type": event_type,
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": 20001,
        "task_external_id": "task_test_0001",
        "event_time": "2030-01-01T07:00:00+07:00",
        "correlation_id": "corr_test_ansvis_0001",
        "attributes": {
            "track_id": 30001,
            "detection_key": "detection_test_0001",
            "status": "online",
            "config_version": "camera_config_v1",
            "detection_count": 1,
        },
    }


@pytest.mark.parametrize(
    ("event_type", "expected_type"),
    [
        ("attendance.face.observed", FaceObservationEvent),
        ("timekeeping.face.observed", FaceObservationEvent),
        ("violation.littering.suspected", SuspectedViolationEvent),
        ("violation.ppe.suspected", SuspectedViolationEvent),
        ("violation.smoking.suspected", SuspectedViolationEvent),
        ("violation.uniform.suspected", SuspectedViolationEvent),
        ("insight.emotion.observed", EmotionInsightEvent),
        ("camera.health.changed", HealthStatusEvent),
        ("task.health.changed", HealthStatusEvent),
    ],
)
def test_parser_maps_approved_event_families(event_type: str, expected_type: type[object]) -> None:
    payload = event_payload(event_type)
    if not event_type.endswith("health.changed"):
        attributes = payload["attributes"]
        assert isinstance(attributes, dict)
        attributes.pop("status")

    event = parse_and_normalize_event(payload)

    assert isinstance(event, expected_type)
    assert event.source_event_id == "10001"
    assert event.camera_external_id == "20001"
    assert event.attributes.track_id == "30001"
    assert event.occurred_at.tzinfo is UTC
    assert event.occurred_at.isoformat() == "2030-01-01T00:00:00+00:00"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"raw_payload": "blocked_test_value"}, "EVENT_SCHEMA_INVALID"),
        ({"event_type": "vendor.unapproved.event"}, "EVENT_TYPE_UNSUPPORTED"),
        ({"event_time": 1_893_456_000}, "EVENT_SCHEMA_INVALID"),
        ({"event_time": "2030-01-01T00:00:00"}, "TIME_TIMESTAMP_NAIVE"),
        ({"event_time": "2030-01-01T00:00:00.1234567Z"}, "TIME_FRACTION_PRECISION"),
    ],
)
def test_parser_rejects_unapproved_shapes(mutation: dict[str, object], expected_code: str) -> None:
    payload = event_payload()
    payload.update(mutation)

    with pytest.raises(AnsvisAdapterError) as raised:
        parse_and_normalize_event(payload)

    assert raised.value.code == expected_code
    assert str(raised.value) == expected_code


def test_parser_rejects_unknown_attribute_without_retaining_it() -> None:
    payload = event_payload()
    attributes = payload["attributes"]
    assert isinstance(attributes, dict)
    attributes["image_base64"] = "blocked_test_value"

    with pytest.raises(AnsvisAdapterError) as raised:
        parse_and_normalize_event(payload)

    assert raised.value.code == "EVENT_SCHEMA_INVALID"
    assert "blocked" not in str(raised.value)


def test_fallback_identity_requires_track_and_detection_key() -> None:
    payload = deepcopy(event_payload())
    payload["source_event_id"] = None
    attributes = payload["attributes"]
    assert isinstance(attributes, dict)
    attributes.pop("detection_key")

    with pytest.raises(AnsvisAdapterError) as raised:
        parse_and_normalize_event(payload)

    assert raised.value.code == "EVENT_FALLBACK_IDENTITY_INSUFFICIENT"


def test_health_event_requires_status() -> None:
    payload = event_payload()
    attributes = payload["attributes"]
    assert isinstance(attributes, dict)
    attributes.pop("status")

    with pytest.raises(AnsvisAdapterError) as raised:
        parse_and_normalize_event(payload)

    assert raised.value.code == "EVENT_SCHEMA_INVALID"


@pytest.mark.parametrize(
    "raw",
    [
        b'{"source_namespace":"ansvis.test.source","source_namespace":"ansvis.test.other"}',
        b'{"confidence":NaN}',
        b"[]",
        b"not-json",
    ],
)
def test_json_loader_rejects_ambiguous_or_non_object_json(raw: bytes) -> None:
    with pytest.raises(AnsvisAdapterError, match="EVENT_SCHEMA_INVALID"):
        load_json_object(raw)


def test_json_loader_accepts_only_the_decoded_object() -> None:
    raw = json.dumps(event_payload(), separators=(",", ":")).encode("utf-8")
    assert load_json_object(raw) == event_payload()


def test_envelope_preflight_extracts_source_without_building_object() -> None:
    raw = (
        b'{"schema_version":"ansvis_http_trigger_v1",'
        b'"source_namespace":"ansvis.test.source","attributes":{"status":"online"}}'
    )

    assert inspect_json_envelope(raw) == "ansvis.test.source"


def test_envelope_preflight_caps_nesting_and_array_length() -> None:
    nested = (
        b'{"source_namespace":"ansvis.test.source","attributes":'
        + b"[" * MAX_JSON_NESTING_DEPTH
        + b"0"
        + b"]" * MAX_JSON_NESTING_DEPTH
        + b"}"
    )
    oversized_array = (
        b'{"source_namespace":"ansvis.test.source","attributes":['
        + b",".join(b"0" for _ in range(MAX_JSON_ARRAY_ITEMS + 1))
        + b"]}"
    )

    for raw in (nested, oversized_array):
        with pytest.raises(AnsvisAdapterError) as raised:
            inspect_json_envelope(raw)
        assert raised.value.code == "EVENT_SCHEMA_INVALID"


def test_json_loader_masks_recursion_and_value_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_with(error: Exception) -> object:
        raise error

    for error in (RecursionError(), ValueError("synthetic parser failure")):
        monkeypatch.setattr(
            "ansvis_adapter.schemas.events.json.loads",
            lambda *args, _error=error, **kwargs: fail_with(_error),
        )
        with pytest.raises(AnsvisAdapterError) as raised:
            load_json_object(b"{}")
        assert raised.value.code == "EVENT_SCHEMA_INVALID"
