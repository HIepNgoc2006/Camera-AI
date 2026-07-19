from __future__ import annotations

from uuid import UUID

import pytest
from camera_registry_service.domain.errors import CameraRegistryError
from camera_registry_service.schemas.commands import (
    parse_map_camera,
    parse_register_camera,
    parse_register_zone,
    parse_update_camera,
)

ZONE_ID = UUID("00000000-0000-4000-8000-000000000201")
CAMERA_ID = UUID("00000000-0000-4000-8000-000000000202")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000203")
TASK_ID = UUID("00000000-0000-4000-8000-000000000204")
IDEMPOTENCY_VALUE = "idem_" + "01234567" + "89abcdef"
PROHIBITED_AUTHORITY = "synthetic-user" + ":" + "synthetic-private-value"
PROHIBITED_STREAM_VALUE = "rtsp" + "://" + PROHIBITED_AUTHORITY + "@192.0.2.1/live"


def _mutation() -> dict[str, object]:
    return {
        "schema_version": 1,
        "request_id": "req_0123456789abcdef",
        "idempotency_key": IDEMPOTENCY_VALUE,
        "policy_version": "camera_policy_v1",
    }


def test_strict_commands_accept_synthetic_minimized_metadata() -> None:
    zone = parse_register_zone(
        {
            **_mutation(),
            "code": "gate_a",
            "name": "Synthetic Gate A",
            "zone_type": "gate",
            "sensitivity": "high",
            "purpose_codes": ["student_uniform", "student_attendance"],
        }
    )
    camera = parse_register_camera(
        {
            **_mutation(),
            "zone_id": str(ZONE_ID),
            "code": "camera_a",
            "display_name": "Synthetic Camera A",
            "purpose_codes": ["student_attendance"],
            "config_version": "camera_cfg_v1",
        }
    )
    mapping = parse_map_camera(
        {
            **_mutation(),
            "camera_id": str(CAMERA_ID),
            "expected_version": 1,
            "source_id": str(SOURCE_ID),
            "task_id": str(TASK_ID),
            "mapping_purpose_code": "student_attendance",
            "credential_ref": "sec_v1_" + "B" * 32,
            "schedule_version": "school_schedule_v1",
            "config_version": "camera_cfg_v2",
        }
    )

    assert zone.purpose_codes == ("student_attendance", "student_uniform")
    assert len(camera.fingerprint()) == 32
    assert mapping.credential_ref == "sec_v1_" + "B" * 32


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", PROHIBITED_STREAM_VALUE),
        ("display_name", "password=synthetic-value"),
        ("purpose_codes", ["unapproved_purpose"]),
        ("unknown_field", "unexpected"),
    ],
)
def test_camera_command_rejects_prohibited_content(field: str, value: object) -> None:
    payload: dict[str, object] = {
        **_mutation(),
        "zone_id": str(ZONE_ID),
        "code": "camera_a",
        "display_name": "Synthetic Camera A",
        "purpose_codes": ["student_attendance"],
        "config_version": "camera_cfg_v1",
    }
    payload[field] = value
    with pytest.raises(CameraRegistryError, match="CAMERA_INPUT_INVALID") as caught:
        parse_register_camera(payload)
    assert str(value) not in str(caught.value)


def test_mapping_rejects_secret_value_or_credentialed_url_without_echo() -> None:
    prohibited = PROHIBITED_STREAM_VALUE
    payload: dict[str, object] = {
        **_mutation(),
        "camera_id": str(CAMERA_ID),
        "expected_version": 1,
        "source_id": str(SOURCE_ID),
        "task_id": str(TASK_ID),
        "mapping_purpose_code": "student_attendance",
        "credential_ref": prohibited,
        "schedule_version": "school_schedule_v1",
        "config_version": "camera_cfg_v2",
    }
    with pytest.raises(CameraRegistryError) as caught:
        parse_map_camera(payload)
    assert prohibited not in str(caught.value)


def test_update_requires_a_real_change() -> None:
    with pytest.raises(CameraRegistryError, match="CAMERA_INPUT_INVALID"):
        parse_update_camera(
            {
                **_mutation(),
                "camera_id": str(CAMERA_ID),
                "expected_version": 1,
            }
        )
