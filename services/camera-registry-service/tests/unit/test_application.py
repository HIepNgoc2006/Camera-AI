from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from camera_registry_service.application.service import CameraRegistryApplicationService
from camera_registry_service.domain.errors import CameraRegistryError
from camera_registry_service.domain.models import (
    Camera,
    CameraAuditIntent,
    CameraChangeRequest,
    CameraStatus,
    RegistryChangeOutcome,
    TrustedRegistryContext,
    Zone,
    ZoneChangeRequest,
    ZoneSensitivity,
    ZoneStatus,
    ZoneType,
)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000401")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000402")
ZONE_ID = UUID("00000000-0000-4000-8000-000000000403")
CAMERA_ID = UUID("00000000-0000-4000-8000-000000000404")


class SequenceIdentifierFactory:
    def __init__(self, values: list[UUID]) -> None:
        self._values = iter(values)

    def __call__(self) -> UUID:
        return next(self._values)


class FakeCameraRegistryRepository:
    def __init__(self) -> None:
        self.zones: dict[UUID, Zone] = {}
        self.cameras: dict[UUID, Camera] = {}

    def create_zone(
        self,
        zone: Zone,
        audit_intent: CameraAuditIntent,
    ) -> RegistryChangeOutcome:
        self.zones[zone.zone_id] = zone
        return RegistryChangeOutcome(zone, audit_intent, duplicate=False)

    def change_zone(
        self,
        request: ZoneChangeRequest,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        raise AssertionError("unexpected fake repository zone change")

    def create_camera(
        self,
        camera: Camera,
        audit_intent: CameraAuditIntent,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        self.cameras[camera.camera_id] = camera
        return RegistryChangeOutcome(camera, audit_intent, duplicate=False)

    def change_camera(
        self,
        request: CameraChangeRequest,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        raise AssertionError("unexpected fake repository camera change")

    def get_zone(self, zone_id: UUID, school_id: UUID) -> Zone | None:
        zone = self.zones.get(zone_id)
        return zone if zone is not None and zone.school_id == school_id else None

    def get_camera(self, camera_id: UUID, school_id: UUID) -> Camera | None:
        camera = self.cameras.get(camera_id)
        return camera if camera is not None and camera.school_id == school_id else None


def _context(
    *,
    allowed_zones: frozenset[UUID] = frozenset({ZONE_ID}),
    assigned: bool = True,
) -> TrustedRegistryContext:
    return TrustedRegistryContext(
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        allowed_zone_ids=allowed_zones,
        allowed_purpose_codes=frozenset({"student_attendance", "student_uniform"}),
        assignment_verified=assigned,
        can_manage_zones=True,
        can_manage_cameras=True,
    )


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


def _mutation(suffix: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "request_id": f"req_{suffix}",
        "idempotency_key": f"idem_{suffix}",
        "policy_version": "camera_policy_v1",
    }


def test_register_zone_binds_tenant_actor_and_minimized_audit_intent() -> None:
    repository = FakeCameraRegistryRepository()
    identifiers = SequenceIdentifierFactory(
        [
            ZONE_ID,
            UUID("00000000-0000-4000-8000-000000000405"),
            UUID("00000000-0000-4000-8000-000000000406"),
        ]
    )
    service = CameraRegistryApplicationService(
        repository,
        clock=lambda: NOW,
        identifier_factory=identifiers,
    )

    outcome = service.register_zone(
        {
            **_mutation("1111111111111111"),
            "code": "gate_a",
            "name": "Synthetic Gate A",
            "zone_type": "gate",
            "sensitivity": "high",
            "purpose_codes": ["student_attendance", "student_uniform"],
        },
        _context(),
    )

    assert outcome.resource.school_id == SCHOOL_ID
    assert outcome.audit_intent.actor_id == ACTOR_ID
    assert outcome.audit_intent.resource_type == "camera_zone"
    assert outcome.audit_intent.changed_fields == ("status", "zone")


def test_register_camera_rechecks_trusted_zone_and_purpose() -> None:
    repository = FakeCameraRegistryRepository()
    repository.zones[ZONE_ID] = _zone()
    identifiers = SequenceIdentifierFactory(
        [
            CAMERA_ID,
            UUID("00000000-0000-4000-8000-000000000407"),
            UUID("00000000-0000-4000-8000-000000000408"),
        ]
    )
    service = CameraRegistryApplicationService(
        repository,
        clock=lambda: NOW,
        identifier_factory=identifiers,
    )

    outcome = service.register_camera(
        {
            **_mutation("2222222222222222"),
            "zone_id": str(ZONE_ID),
            "code": "camera_a",
            "display_name": "Synthetic Camera A",
            "purpose_codes": ["student_attendance"],
            "config_version": "camera_cfg_v1",
        },
        _context(),
    )

    assert isinstance(outcome.resource, Camera)
    assert outcome.resource.source_id is None
    assert outcome.resource.credential_ref is None
    assert outcome.audit_intent.change_code == "camera_registered"


def test_unverified_assignment_denies_without_calling_repository_mutation() -> None:
    repository = FakeCameraRegistryRepository()
    repository.zones[ZONE_ID] = _zone()
    service = CameraRegistryApplicationService(repository, clock=lambda: NOW)

    with pytest.raises(CameraRegistryError, match="CAMERA_AUTHORITY_DENIED"):
        service.register_camera(
            {
                **_mutation("3333333333333333"),
                "zone_id": str(ZONE_ID),
                "code": "camera_a",
                "display_name": "Synthetic Camera A",
                "purpose_codes": ["student_attendance"],
                "config_version": "camera_cfg_v1",
            },
            _context(assigned=False),
        )
    assert repository.cameras == {}


def test_lookup_hides_camera_outside_trusted_zone_scope() -> None:
    repository = FakeCameraRegistryRepository()
    repository.cameras[CAMERA_ID] = Camera(
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
    service = CameraRegistryApplicationService(repository, clock=lambda: NOW)

    with pytest.raises(CameraRegistryError, match="CAMERA_NOT_FOUND"):
        service.get_camera(
            CAMERA_ID,
            _context(allowed_zones=frozenset({UUID("00000000-0000-4000-8000-000000000409")})),
        )
