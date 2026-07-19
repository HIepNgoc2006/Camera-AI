"""Trusted-context Camera Registry use cases with no public HTTP boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from camera_registry_service.application.ports import CameraRegistryRepository
from camera_registry_service.domain.errors import CameraRegistryError
from camera_registry_service.domain.models import (
    AUDIT_ACTION,
    AUDIT_PURPOSE_CODE,
    Camera,
    CameraAuditIntent,
    CameraChangeOperation,
    CameraChangeRequest,
    CameraStatus,
    ChangeMetadata,
    RegistryChangeOutcome,
    TrustedRegistryContext,
    Zone,
    ZoneChangeOperation,
    ZoneChangeRequest,
    ZoneStatus,
    authorize_zone_compatibility,
)
from camera_registry_service.schemas.commands import (
    MutationModel,
    parse_deactivate_camera,
    parse_deactivate_zone,
    parse_map_camera,
    parse_register_camera,
    parse_register_zone,
    parse_update_camera,
    parse_update_zone,
)

Clock = Callable[[], datetime]
IdentifierFactory = Callable[[], UUID]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CameraRegistryApplicationService:
    """Register, change, map, deactivate, and look up tenant camera metadata."""

    def __init__(
        self,
        repository: CameraRegistryRepository,
        *,
        clock: Clock = _utc_now,
        identifier_factory: IdentifierFactory = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifier_factory = identifier_factory

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise CameraRegistryError("CAMERA_INPUT_INVALID")
        return value

    def _id(self) -> UUID:
        value = self._identifier_factory()
        if value.int == 0:
            raise CameraRegistryError("CAMERA_INPUT_INVALID")
        return value

    def _metadata(
        self,
        command: MutationModel,
        context: TrustedRegistryContext,
        changed_at: datetime,
    ) -> ChangeMetadata:
        return ChangeMetadata(
            source_event_id=self._id(),
            audit_intent_id=self._id(),
            school_id=context.school_id,
            actor_id=context.actor_id,
            request_id=command.request_id,
            idempotency_key=command.idempotency_key,
            request_fingerprint=command.fingerprint(),
            policy_version=command.policy_version,
            changed_at=changed_at,
        )

    @staticmethod
    def _create_intent(
        *,
        metadata: ChangeMetadata,
        resource_type: str,
        resource_id: UUID,
        change_code: str,
        changed_fields: tuple[str, ...],
        zone_id: UUID,
        config_version: str | None,
        state_after: str,
    ) -> CameraAuditIntent:
        return CameraAuditIntent(
            audit_intent_id=metadata.audit_intent_id,
            source_event_id=metadata.source_event_id,
            school_id=metadata.school_id,
            actor_id=metadata.actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            change_code=change_code,
            changed_fields=changed_fields,
            zone_id=zone_id,
            source_id=None,
            task_id=None,
            request_id=metadata.request_id,
            idempotency_key=metadata.idempotency_key,
            request_fingerprint=metadata.request_fingerprint,
            state_before=None,
            state_after=state_after,
            config_version=config_version,
            schedule_version=None,
            policy_version=metadata.policy_version,
            reason_code=None,
            resulting_version=1,
            created_at=metadata.changed_at,
            action=AUDIT_ACTION,
            purpose_code=AUDIT_PURPOSE_CODE,
        )

    def register_zone(
        self,
        payload: Mapping[str, object],
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        item = parse_register_zone(payload)
        context.authorize_zone_management()
        if not set(item.purpose_codes).issubset(context.allowed_purpose_codes):
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        now = self._now()
        zone = Zone(
            zone_id=self._id(),
            school_id=context.school_id,
            code=item.code,
            name=item.name,
            zone_type=item.zone_type,
            sensitivity=item.sensitivity,
            purpose_codes=tuple(item.purpose_codes),
            status=ZoneStatus.ACTIVE,
            deactivated_at=None,
            created_at=now,
            updated_at=now,
            row_version=1,
        )
        metadata = self._metadata(item, context, now)
        intent = self._create_intent(
            metadata=metadata,
            resource_type="camera_zone",
            resource_id=zone.zone_id,
            change_code="zone_registered",
            changed_fields=("status", "zone"),
            zone_id=zone.zone_id,
            config_version=None,
            state_after=zone.status.value,
        )
        return self._repository.create_zone(zone, intent)

    def update_zone(
        self,
        payload: Mapping[str, object],
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        item = parse_update_zone(payload)
        context.authorize_zone_management(item.zone_id)
        if item.purpose_codes is not None and not set(item.purpose_codes).issubset(
            context.allowed_purpose_codes
        ):
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        now = self._now()
        request = ZoneChangeRequest(
            metadata=self._metadata(item, context, now),
            zone_id=item.zone_id,
            operation=ZoneChangeOperation.UPDATE,
            expected_version=item.expected_version,
            name=item.name,
            purpose_codes=None if item.purpose_codes is None else tuple(item.purpose_codes),
        )
        return self._repository.change_zone(request, context)

    def deactivate_zone(
        self,
        payload: Mapping[str, object],
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        item = parse_deactivate_zone(payload)
        context.authorize_zone_management(item.zone_id)
        now = self._now()
        request = ZoneChangeRequest(
            metadata=self._metadata(item, context, now),
            zone_id=item.zone_id,
            operation=ZoneChangeOperation.DEACTIVATE,
            expected_version=item.expected_version,
            reason_code=item.reason_code,
        )
        return self._repository.change_zone(request, context)

    def register_camera(
        self,
        payload: Mapping[str, object],
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        item = parse_register_camera(payload)
        context.authorize_zone(item.zone_id, tuple(item.purpose_codes))
        zone = self._repository.get_zone(item.zone_id, context.school_id)
        if zone is None:
            raise CameraRegistryError("CAMERA_ZONE_NOT_FOUND")
        authorize_zone_compatibility(zone, tuple(item.purpose_codes))
        now = self._now()
        camera = Camera(
            camera_id=self._id(),
            school_id=context.school_id,
            zone_id=item.zone_id,
            code=item.code,
            display_name=item.display_name,
            purpose_codes=tuple(item.purpose_codes),
            source_id=None,
            task_id=None,
            mapping_purpose_code=None,
            credential_ref=None,
            schedule_version=None,
            config_version=item.config_version,
            status=CameraStatus.PENDING,
            last_seen_at=None,
            deactivated_at=None,
            created_at=now,
            updated_at=now,
            row_version=1,
        )
        metadata = self._metadata(item, context, now)
        intent = self._create_intent(
            metadata=metadata,
            resource_type="camera",
            resource_id=camera.camera_id,
            change_code="camera_registered",
            changed_fields=("config", "purpose", "status", "zone"),
            zone_id=camera.zone_id,
            config_version=camera.config_version,
            state_after=camera.status.value,
        )
        return self._repository.create_camera(camera, intent, context)

    def update_camera(
        self,
        payload: Mapping[str, object],
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        item = parse_update_camera(payload)
        if not context.assignment_verified or not context.can_manage_cameras:
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        if item.zone_id is not None:
            context.authorize_zone(item.zone_id, tuple(item.purpose_codes or ()))
        if item.purpose_codes is not None and not set(item.purpose_codes).issubset(
            context.allowed_purpose_codes
        ):
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        now = self._now()
        request = CameraChangeRequest(
            metadata=self._metadata(item, context, now),
            camera_id=item.camera_id,
            operation=CameraChangeOperation.UPDATE,
            expected_version=item.expected_version,
            zone_id=item.zone_id,
            display_name=item.display_name,
            purpose_codes=None if item.purpose_codes is None else tuple(item.purpose_codes),
            config_version=item.config_version,
        )
        return self._repository.change_camera(request, context)

    def map_camera(
        self,
        payload: Mapping[str, object],
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        item = parse_map_camera(payload)
        if (
            not context.assignment_verified
            or not context.can_manage_cameras
            or item.mapping_purpose_code not in context.allowed_purpose_codes
        ):
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        now = self._now()
        request = CameraChangeRequest(
            metadata=self._metadata(item, context, now),
            camera_id=item.camera_id,
            operation=CameraChangeOperation.MAP,
            expected_version=item.expected_version,
            source_id=item.source_id,
            task_id=item.task_id,
            mapping_purpose_code=item.mapping_purpose_code,
            credential_ref=item.credential_ref,
            schedule_version=item.schedule_version,
            config_version=item.config_version,
        )
        return self._repository.change_camera(request, context)

    def deactivate_camera(
        self,
        payload: Mapping[str, object],
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        item = parse_deactivate_camera(payload)
        if not context.assignment_verified or not context.can_manage_cameras:
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        now = self._now()
        request = CameraChangeRequest(
            metadata=self._metadata(item, context, now),
            camera_id=item.camera_id,
            operation=CameraChangeOperation.DEACTIVATE,
            expected_version=item.expected_version,
            reason_code=item.reason_code,
        )
        return self._repository.change_camera(request, context)

    def get_zone(self, zone_id: UUID, context: TrustedRegistryContext) -> Zone:
        context.authorize_zone_management(zone_id)
        zone = self._repository.get_zone(zone_id, context.school_id)
        if zone is None:
            raise CameraRegistryError("CAMERA_ZONE_NOT_FOUND")
        return zone

    def get_camera(self, camera_id: UUID, context: TrustedRegistryContext) -> Camera:
        if not context.assignment_verified or not context.can_manage_cameras:
            raise CameraRegistryError("CAMERA_NOT_FOUND")
        camera = self._repository.get_camera(camera_id, context.school_id)
        if camera is None:
            raise CameraRegistryError("CAMERA_NOT_FOUND")
        if camera.zone_id not in context.allowed_zone_ids or not set(camera.purpose_codes).issubset(
            context.allowed_purpose_codes
        ):
            raise CameraRegistryError("CAMERA_NOT_FOUND")
        return camera
