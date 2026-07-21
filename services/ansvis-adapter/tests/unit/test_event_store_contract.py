from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.event_store import (
    _detection_attributes,
    _fingerprint,
    _outbox_payload,
    _safe_metadata,
)
from ansvis_adapter.schemas.events import parse_and_normalize_event

EVENT_ID = UUID("00000000-0000-4000-8000-000000000631")
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000632")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000633")
CAMERA_ID = UUID("00000000-0000-4000-8000-000000000634")
TASK_ID = UUID("00000000-0000-4000-8000-000000000635")


def _face_event() -> NormalizedAnsvisEvent:
    return parse_and_normalize_event(
        {
            "schema_version": "ansvis_http_trigger_v1",
            "source_namespace": "ansvis.test.source",
            "source_event_id": "event_test_minimized_0001",
            "event_type": "attendance.face.observed",
            "tenant_ref": "tenant_test_0001",
            "school_ref": "school_test_0001",
            "camera_external_id": "camera_test_0001",
            "task_external_id": "task_test_0001",
            "event_time": "2026-07-21T10:00:00Z",
            "correlation_id": "corr_test_minimized_0001",
            "attributes": {
                "track_id": "track_test_0001",
                "detection_key": "detection_test_0001",
                "subject_external_id": "synthetic_subject_reference",
                "confidence": 0.875,
                "model_version": "face_model_v1",
                "config_version": "camera_config_v1",
                "detection_count": 1,
            },
        }
    )


def test_normalized_storage_and_outbox_contract_exclude_subject_and_media_shapes() -> None:
    event = _face_event()
    payload = _outbox_payload(
        event,
        event_id=EVENT_ID,
        school_id=SCHOOL_ID,
        source_id=SOURCE_ID,
        camera_id=CAMERA_ID,
        task_id=TASK_ID,
        consent_status="not_evaluated",
    )
    serialized = json.dumps(
        {
            "metadata": _safe_metadata(event),
            "detection": _detection_attributes(event),
            "outbox": payload,
        },
        sort_keys=True,
    ).casefold()

    assert payload["schema_version"] == "normalized_outbox_v1"
    assert payload["metadata"] == {
        "schema_version": "event_metadata_v1",
        "detection_count": 1,
    }
    assert all(
        marker not in serialized
        for marker in (
            "authorization",
            "base64",
            "embedding",
            "face_image",
            "media_url",
            "raw_payload",
            "rtsp",
            "subject_external_id",
            "synthetic_subject_reference",
        )
    )


def test_database_checksum_adapter_accepts_driver_bytes_and_rejects_invalid_values() -> None:
    checksum = bytes(range(32))
    expected = f"sha256:{checksum.hex()}"
    assert _fingerprint(checksum) == expected
    assert _fingerprint(bytearray(checksum)) == expected
    assert _fingerprint(memoryview(checksum)) == expected
    with pytest.raises(AnsvisAdapterError, match="EVENT_DURABLE_RECEIPT_UNAVAILABLE"):
        _fingerprint(b"too-short")


def test_face_fixture_uses_only_synthetic_current_data() -> None:
    event = _face_event()
    assert event.occurred_at == datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
