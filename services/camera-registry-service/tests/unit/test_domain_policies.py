from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from camera_registry_service.domain.errors import CameraRegistryError
from camera_registry_service.domain.models import (
    Camera,
    CameraChangeOperation,
    CameraChangeRequest,
    CameraStatus,
    ChangeMetadata,
    TrustedRegistryContext,
    Zone,
    ZoneSensitivity,
    ZoneStatus,
    ZoneType,
    authorize_zone_compatibility,
    deactivate_camera,
    deactivate_zone,
    map_camera,
)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000101")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000102")
ZONE_ID = UUID("00000000-0000-4000-8000-000000000103")
CAMERA_ID = UUID("00000000-0000-4000-8000-000000000104")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000105")
TASK_ID = UUID("00000000-0000-4000-8000-000000000106")
IDEMPOTENCY_VALUE = "idem_" + "01234567" + "89abcdef"


def _zone() -> Zone:
    return Zone(
        zone_id=ZONE_ID,
        school_id=SCHOOL_ID,
        code="gate_a",
        name="Synthetic Gate A",
        zone_type=ZoneType.GATE,
        sensitivity=ZoneSensitivity.HIGH,
        purpose_codes=("student_attendance", "student_uniform"),
        status=ZoneStatus.ACTIVE,
        deactivated_at=None,
        created_at=NOW,
        updated_at=NOW,
        row_version=1,
    )


def _camera() -> Camera:
    return Camera(
        camera_id=CAMERA_ID,
        school_id=SCHOOL_ID,
        zone_id=ZONE_ID,
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


def _metadata() -> ChangeMetadata:
    return ChangeMetadata(
        source_event_id=UUID("00000000-0000-4000-8000-000000000107"),
        audit_intent_id=UUID("00000000-0000-4000-8000-000000000108"),
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        request_id="req_0123456789abcdef",
        idempotency_key=IDEMPOTENCY_VALUE,
        request_fingerprint=b"x" * 32,
        policy_version="camera_policy_v1",
        changed_at=NOW,
    )


def test_zone_and_camera_lifecycle_are_fail_closed_and_terminal() -> None:
    inactive = deactivate_zone(_zone(), changed_at=NOW)
    disabled = deactivate_camera(_camera(), changed_at=NOW)

    assert inactive.status is ZoneStatus.INACTIVE
    assert inactive.row_version == 2
    assert disabled.status is CameraStatus.DISABLED
    assert disabled.row_version == 2
    with pytest.raises(CameraRegistryError, match="CAMERA_TRANSITION_DENIED"):
        deactivate_zone(inactive, changed_at=NOW)
    with pytest.raises(CameraRegistryError, match="CAMERA_TRANSITION_DENIED"):
        deactivate_camera(disabled, changed_at=NOW)


def test_zone_purpose_compatibility_and_trusted_assignment_are_enforced() -> None:
    zone = _zone()
    context = TrustedRegistryContext(
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        allowed_zone_ids=frozenset({ZONE_ID}),
        allowed_purpose_codes=frozenset({"student_attendance"}),
        assignment_verified=True,
        can_manage_zones=True,
        can_manage_cameras=True,
    )

    authorize_zone_compatibility(zone, ("student_attendance",))
    context.authorize_zone(ZONE_ID, ("student_attendance",))
    with pytest.raises(CameraRegistryError, match="CAMERA_PURPOSE_DENIED"):
        authorize_zone_compatibility(zone, ("kitchen_ppe",))
    with pytest.raises(CameraRegistryError, match="CAMERA_AUTHORITY_DENIED"):
        context.authorize_zone(ZONE_ID, ("student_uniform",))


def test_mapping_accepts_only_complete_opaque_references_and_approved_purpose() -> None:
    request = CameraChangeRequest(
        metadata=_metadata(),
        camera_id=CAMERA_ID,
        operation=CameraChangeOperation.MAP,
        expected_version=1,
        source_id=SOURCE_ID,
        task_id=TASK_ID,
        mapping_purpose_code="student_attendance",
        credential_ref="sec_v1_" + "A" * 32,
        schedule_version="school_schedule_v1",
        config_version="camera_cfg_v2",
    )

    mapped = map_camera(_camera(), request)

    assert mapped.source_id == SOURCE_ID
    assert mapped.task_id == TASK_ID
    assert mapped.credential_ref == "sec_v1_" + "A" * 32
    assert mapped.row_version == 2


def test_domain_rejects_url_shaped_credential_without_echoing_it() -> None:
    authority = "synthetic-user" + ":" + "synthetic-private-value"
    prohibited = "rtsp" + "://" + authority + "@192.0.2.1/live"
    with pytest.raises(CameraRegistryError) as caught:
        replace(_camera(), credential_ref=prohibited)
    assert prohibited not in str(caught.value)
