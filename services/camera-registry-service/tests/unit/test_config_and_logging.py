from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from camera_registry_service.config import (
    CameraRegistryConfigurationError,
    load_database_settings,
)
from camera_registry_service.domain.models import (
    Camera,
    CameraAuditIntent,
    CameraStatus,
    RegistryChangeOutcome,
)
from camera_registry_service.logging import safe_change_log_fields

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
IDEMPOTENCY_VALUE = "idem_" + "01234567" + "89abcdef"


def test_database_configuration_is_fail_closed_and_redacted() -> None:
    scheme = "postgresql+psycopg"
    test_user_info = "synthetic-user" + ":" + "synthetic-private-value"
    test_uri = f"{scheme}://{test_user_info}@127.0.0.1:55435/Camera_AI_camera_test"
    settings = load_database_settings(
        {
            "APP_ENV": "test",
            "CAMERA_DATABASE_URI": test_uri,
        }
    )
    assert settings.environment == "test"
    assert "synthetic-private-value" not in repr(settings)

    placeholder_user_info = "placeholder-user" + ":" + "change_me"
    placeholder_uri = f"{scheme}://{placeholder_user_info}@example.invalid/Camera_AI_example"
    with pytest.raises(CameraRegistryConfigurationError) as caught:
        load_database_settings(
            {
                "APP_ENV": "production",
                "CAMERA_DATABASE_URI": placeholder_uri,
            }
        )
    assert "change_me" not in str(caught.value)


def test_safe_log_fields_exclude_topology_credentials_and_identifiers() -> None:
    camera = Camera(
        camera_id=UUID("00000000-0000-4000-8000-000000000301"),
        school_id=UUID("00000000-0000-4000-8000-000000000302"),
        zone_id=UUID("00000000-0000-4000-8000-000000000303"),
        code="camera_a",
        display_name="Synthetic Camera A",
        purpose_codes=("student_attendance",),
        source_id=None,
        task_id=None,
        mapping_purpose_code=None,
        credential_ref=None,
        schedule_version=None,
        config_version="camera_cfg_v1",
        status=CameraStatus.PENDING,
        last_seen_at=None,
        deactivated_at=None,
        created_at=NOW,
        updated_at=NOW,
        row_version=1,
    )
    intent = CameraAuditIntent(
        audit_intent_id=UUID("00000000-0000-4000-8000-000000000304"),
        source_event_id=UUID("00000000-0000-4000-8000-000000000305"),
        school_id=camera.school_id,
        actor_id=UUID("00000000-0000-4000-8000-000000000306"),
        resource_type="camera",
        resource_id=camera.camera_id,
        change_code="camera_registered",
        changed_fields=("status", "zone"),
        zone_id=camera.zone_id,
        source_id=None,
        task_id=None,
        request_id="req_0123456789abcdef",
        idempotency_key=IDEMPOTENCY_VALUE,
        request_fingerprint=b"x" * 32,
        state_before=None,
        state_after="pending",
        config_version="camera_cfg_v1",
        schedule_version=None,
        policy_version="camera_policy_v1",
        reason_code=None,
        resulting_version=1,
        created_at=NOW,
    )

    fields = safe_change_log_fields(RegistryChangeOutcome(camera, intent, False), "register")

    assert set(fields) == {
        "service_name",
        "operation",
        "action",
        "change_code",
        "resource_type",
        "status",
        "request_id",
        "result",
    }
    serialized = repr(fields)
    for forbidden in (
        str(camera.camera_id),
        str(camera.school_id),
        str(camera.zone_id),
        "credential_ref",
        "source_id",
        "task_id",
    ):
        assert forbidden not in serialized
