"""Tenant-scoped PostgreSQL repository with atomic camera audit intents."""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from camera_registry_service.domain.errors import CameraRegistryError
from camera_registry_service.domain.models import (
    AUDIT_ACTION,
    AUDIT_PURPOSE_CODE,
    Camera,
    CameraAuditIntent,
    CameraChangeOperation,
    CameraChangeRequest,
    CameraStatus,
    RegistryChangeOutcome,
    TrustedRegistryContext,
    Zone,
    ZoneChangeOperation,
    ZoneChangeRequest,
    ZoneSensitivity,
    ZoneStatus,
    ZoneType,
    authorize_zone_compatibility,
    deactivate_camera,
    deactivate_zone,
    map_camera,
    update_camera,
    update_zone,
)
from camera_registry_service.infrastructure.tables import (
    camera_audit_outbox,
    cameras,
    zones,
)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else _uuid(value)


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CameraRegistryError("CAMERA_UNAVAILABLE")
    return value


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _integrity_error_code(error: IntegrityError, default: str) -> str:
    diagnostic = getattr(error.orig, "diag", None)
    constraint = getattr(diagnostic, "constraint_name", None)
    if isinstance(constraint, str):
        if constraint.startswith("uq_camera_outbox"):
            return "CAMERA_DUPLICATE_CONFLICT"
        if constraint == "uq_camera_cameras_primary_mapping":
            return "CAMERA_MAPPING_CONFLICT"
    return default


def _strings(value: object) -> tuple[str, ...]:
    return tuple(cast(list[str], value))


def _zone(row: RowMapping) -> Zone:
    return Zone(
        zone_id=_uuid(row["zone_id"]),
        school_id=_uuid(row["school_id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        zone_type=ZoneType(str(row["zone_type"])),
        sensitivity=ZoneSensitivity(str(row["sensitivity"])),
        purpose_codes=_strings(row["purpose_codes"]),
        status=ZoneStatus(str(row["status"])),
        deactivated_at=_optional_datetime(row["deactivated_at"]),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        row_version=int(cast(int, row["row_version"])),
    )


def _camera(row: RowMapping) -> Camera:
    return Camera(
        camera_id=_uuid(row["camera_id"]),
        school_id=_uuid(row["school_id"]),
        zone_id=_uuid(row["zone_id"]),
        code=str(row["code"]),
        display_name=str(row["display_name"]),
        purpose_codes=_strings(row["purpose_codes"]),
        source_id=_optional_uuid(row["source_id"]),
        task_id=_optional_uuid(row["task_id"]),
        mapping_purpose_code=(
            None if row["mapping_purpose_code"] is None else str(row["mapping_purpose_code"])
        ),
        credential_ref=None if row["credential_ref"] is None else str(row["credential_ref"]),
        schedule_version=(
            None if row["schedule_version"] is None else str(row["schedule_version"])
        ),
        config_version=str(row["config_version"]),
        status=CameraStatus(str(row["status"])),
        last_seen_at=_optional_datetime(row["last_seen_at"]),
        deactivated_at=_optional_datetime(row["deactivated_at"]),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        row_version=int(cast(int, row["row_version"])),
    )


def _intent(row: RowMapping) -> CameraAuditIntent:
    return CameraAuditIntent(
        audit_intent_id=_uuid(row["audit_intent_id"]),
        source_event_id=_uuid(row["source_event_id"]),
        school_id=_uuid(row["school_id"]),
        actor_id=_uuid(row["actor_id"]),
        resource_type=str(row["resource_type"]),
        resource_id=_uuid(row["resource_id"]),
        change_code=str(row["change_code"]),
        changed_fields=_strings(row["changed_fields"]),
        zone_id=_optional_uuid(row["zone_id"]),
        source_id=_optional_uuid(row["source_id"]),
        task_id=_optional_uuid(row["task_id"]),
        request_id=str(row["request_id"]),
        idempotency_key=str(row["idempotency_key"]),
        request_fingerprint=bytes(row["request_fingerprint"]),
        state_before=None if row["state_before"] is None else str(row["state_before"]),
        state_after=str(row["state_after"]),
        config_version=(None if row["config_version"] is None else str(row["config_version"])),
        schedule_version=(
            None if row["schedule_version"] is None else str(row["schedule_version"])
        ),
        policy_version=str(row["policy_version"]),
        reason_code=None if row["reason_code"] is None else str(row["reason_code"]),
        resulting_version=int(cast(int, row["resulting_version"])),
        created_at=_datetime(row["created_at"]),
        action=str(row["action"]),
        purpose_code=str(row["purpose_code"]),
        result=str(row["result"]),
    )


def _zone_values(item: Zone) -> dict[str, object]:
    return {
        "zone_id": item.zone_id,
        "school_id": item.school_id,
        "code": item.code,
        "name": item.name,
        "zone_type": item.zone_type.value,
        "sensitivity": item.sensitivity.value,
        "purpose_codes": list(item.purpose_codes),
        "status": item.status.value,
        "deactivated_at": item.deactivated_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "row_version": item.row_version,
    }


def _camera_values(item: Camera) -> dict[str, object]:
    return {
        "camera_id": item.camera_id,
        "school_id": item.school_id,
        "zone_id": item.zone_id,
        "code": item.code,
        "display_name": item.display_name,
        "purpose_codes": list(item.purpose_codes),
        "source_id": item.source_id,
        "task_id": item.task_id,
        "mapping_purpose_code": item.mapping_purpose_code,
        "credential_ref": item.credential_ref,
        "schedule_version": item.schedule_version,
        "config_version": item.config_version,
        "status": item.status.value,
        "last_seen_at": item.last_seen_at,
        "deactivated_at": item.deactivated_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "row_version": item.row_version,
    }


def _intent_values(item: CameraAuditIntent) -> dict[str, object]:
    return {
        "audit_intent_id": item.audit_intent_id,
        "event_schema_version": 1,
        "source_service": "camera-registry-service",
        "source_event_id": item.source_event_id,
        "school_id": item.school_id,
        "actor_id": item.actor_id,
        "action": item.action,
        "purpose_code": item.purpose_code,
        "resource_type": item.resource_type,
        "resource_id": item.resource_id,
        "change_code": item.change_code,
        "changed_fields": list(item.changed_fields),
        "zone_id": item.zone_id,
        "source_id": item.source_id,
        "task_id": item.task_id,
        "request_id": item.request_id,
        "idempotency_key": item.idempotency_key,
        "request_fingerprint": item.request_fingerprint,
        "result": item.result,
        "state_before": item.state_before,
        "state_after": item.state_after,
        "config_version": item.config_version,
        "schedule_version": item.schedule_version,
        "policy_version": item.policy_version,
        "reason_code": item.reason_code,
        "resulting_version": item.resulting_version,
        "delivery_status": "pending",
        "published_at": None,
        "attempt_count": 0,
        "created_at": item.created_at,
    }


def _existing_outcome(
    connection: Connection,
    school_id: UUID,
    idempotency_key: str,
    fingerprint: bytes,
) -> RegistryChangeOutcome | None:
    row = (
        connection.execute(
            sa.select(camera_audit_outbox).where(
                camera_audit_outbox.c.school_id == school_id,
                camera_audit_outbox.c.idempotency_key == idempotency_key,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    intent = _intent(row)
    if not hmac.compare_digest(intent.request_fingerprint, fingerprint):
        raise CameraRegistryError("CAMERA_DUPLICATE_CONFLICT")
    table = zones if intent.resource_type == "camera_zone" else cameras
    identifier = table.c.zone_id if table is zones else table.c.camera_id
    resource_row = (
        connection.execute(
            sa.select(table).where(
                table.c.school_id == school_id,
                identifier == intent.resource_id,
            )
        )
        .mappings()
        .one()
    )
    resource = _zone(resource_row) if table is zones else _camera(resource_row)
    return RegistryChangeOutcome(resource, intent, duplicate=True)


def _change_intent(
    request: ZoneChangeRequest | CameraChangeRequest,
    current: Zone | Camera,
    updated: Zone | Camera,
    changed_fields: tuple[str, ...],
) -> CameraAuditIntent:
    metadata = request.metadata
    if isinstance(updated, Zone):
        resource_type = "camera_zone"
        resource_id = updated.zone_id
        zone_id = updated.zone_id
        source_id = None
        task_id = None
        config_version = None
        schedule_version = None
    else:
        resource_type = "camera"
        resource_id = updated.camera_id
        zone_id = updated.zone_id
        source_id = updated.source_id
        task_id = updated.task_id
        config_version = updated.config_version
        schedule_version = updated.schedule_version
    return CameraAuditIntent(
        audit_intent_id=metadata.audit_intent_id,
        source_event_id=metadata.source_event_id,
        school_id=metadata.school_id,
        actor_id=metadata.actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        change_code=request.operation.value,
        changed_fields=changed_fields,
        zone_id=zone_id,
        source_id=source_id,
        task_id=task_id,
        request_id=metadata.request_id,
        idempotency_key=metadata.idempotency_key,
        request_fingerprint=metadata.request_fingerprint,
        state_before=current.status.value,
        state_after=updated.status.value,
        config_version=config_version,
        schedule_version=schedule_version,
        policy_version=metadata.policy_version,
        reason_code=request.reason_code,
        resulting_version=updated.row_version,
        created_at=metadata.changed_at,
        action=AUDIT_ACTION,
        purpose_code=AUDIT_PURPOSE_CODE,
    )


def _lock_idempotency(connection: Connection, school_id: UUID, key: str) -> None:
    connection.execute(
        sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
        {"identity": f"{school_id}:{key}"},
    )


def _validate_context(
    request: ZoneChangeRequest | CameraChangeRequest,
    context: TrustedRegistryContext,
) -> None:
    if (
        request.metadata.school_id != context.school_id
        or request.metadata.actor_id != context.actor_id
    ):
        raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")


def _locked_zone(connection: Connection, school_id: UUID, zone_id: UUID) -> Zone:
    row = (
        connection.execute(
            sa.select(zones)
            .where(zones.c.school_id == school_id, zones.c.zone_id == zone_id)
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise CameraRegistryError("CAMERA_ZONE_NOT_FOUND")
    return _zone(row)


def _locked_camera(connection: Connection, school_id: UUID, camera_id: UUID) -> Camera:
    row = (
        connection.execute(
            sa.select(cameras)
            .where(cameras.c.school_id == school_id, cameras.c.camera_id == camera_id)
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise CameraRegistryError("CAMERA_NOT_FOUND")
    return _camera(row)


class SqlAlchemyCameraRegistryRepository:
    """Own only the camera schema and never resolve logical references cross-schema."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_zone(
        self,
        zone: Zone,
        audit_intent: CameraAuditIntent,
    ) -> RegistryChangeOutcome:
        if (
            zone.school_id != audit_intent.school_id
            or zone.zone_id != audit_intent.resource_id
            or zone.zone_id != audit_intent.zone_id
            or audit_intent.resource_type != "camera_zone"
        ):
            raise CameraRegistryError("CAMERA_INPUT_INVALID")
        try:
            with self._engine.begin() as connection:
                _lock_idempotency(connection, zone.school_id, audit_intent.idempotency_key)
                existing = _existing_outcome(
                    connection,
                    zone.school_id,
                    audit_intent.idempotency_key,
                    audit_intent.request_fingerprint,
                )
                if existing is not None:
                    return existing
                connection.execute(sa.insert(zones).values(**_zone_values(zone)))
                connection.execute(
                    sa.insert(camera_audit_outbox).values(**_intent_values(audit_intent))
                )
                return RegistryChangeOutcome(zone, audit_intent, duplicate=False)
        except CameraRegistryError:
            raise
        except IntegrityError as exc:
            raise CameraRegistryError(
                _integrity_error_code(exc, "CAMERA_ZONE_ALREADY_EXISTS")
            ) from None
        except SQLAlchemyError:
            raise CameraRegistryError("CAMERA_UNAVAILABLE") from None

    def change_zone(
        self,
        request: ZoneChangeRequest,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        _validate_context(request, context)
        try:
            with self._engine.begin() as connection:
                _lock_idempotency(
                    connection, request.metadata.school_id, request.metadata.idempotency_key
                )
                existing = _existing_outcome(
                    connection,
                    request.metadata.school_id,
                    request.metadata.idempotency_key,
                    request.metadata.request_fingerprint,
                )
                if existing is not None:
                    return existing
                current = _locked_zone(connection, context.school_id, request.zone_id)
                context.authorize_zone_management(current.zone_id)
                if current.row_version != request.expected_version:
                    raise CameraRegistryError("CAMERA_VERSION_CONFLICT")
                changed_fields: tuple[str, ...]
                active_camera_rows = list(
                    connection.execute(
                        sa.select(cameras.c.purpose_codes)
                        .where(
                            cameras.c.school_id == context.school_id,
                            cameras.c.zone_id == current.zone_id,
                            cameras.c.status != CameraStatus.DISABLED.value,
                        )
                        .with_for_update()
                    )
                )
                if request.operation is ZoneChangeOperation.DEACTIVATE:
                    if active_camera_rows:
                        raise CameraRegistryError("CAMERA_ZONE_IN_USE")
                    updated = deactivate_zone(current, changed_at=request.metadata.changed_at)
                    changed_fields = ("status", "zone")
                else:
                    target_purposes = (
                        current.purpose_codes
                        if request.purpose_codes is None
                        else request.purpose_codes
                    )
                    if not set(target_purposes).issubset(context.allowed_purpose_codes):
                        raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
                    for row in active_camera_rows:
                        if not set(_strings(row[0])).issubset(target_purposes):
                            raise CameraRegistryError("CAMERA_PURPOSE_DENIED")
                    if request.name == current.name and target_purposes == current.purpose_codes:
                        raise CameraRegistryError("CAMERA_NO_CHANGE")
                    updated = update_zone(
                        current,
                        name=request.name,
                        purpose_codes=request.purpose_codes,
                        changed_at=request.metadata.changed_at,
                    )
                    fields = ["metadata"] if request.name is not None else []
                    if request.purpose_codes is not None:
                        fields.append("purpose")
                    changed_fields = tuple(fields)
                result = connection.execute(
                    sa.update(zones)
                    .where(
                        zones.c.school_id == context.school_id,
                        zones.c.zone_id == current.zone_id,
                        zones.c.row_version == request.expected_version,
                    )
                    .values(**_zone_values(updated))
                )
                if result.rowcount != 1:
                    raise CameraRegistryError("CAMERA_VERSION_CONFLICT")
                intent = _change_intent(request, current, updated, changed_fields)
                connection.execute(sa.insert(camera_audit_outbox).values(**_intent_values(intent)))
                return RegistryChangeOutcome(updated, intent, duplicate=False)
        except CameraRegistryError:
            raise
        except IntegrityError as exc:
            raise CameraRegistryError(
                _integrity_error_code(exc, "CAMERA_DUPLICATE_CONFLICT")
            ) from None
        except SQLAlchemyError:
            raise CameraRegistryError("CAMERA_UNAVAILABLE") from None

    def create_camera(
        self,
        camera: Camera,
        audit_intent: CameraAuditIntent,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        if (
            camera.school_id != context.school_id
            or audit_intent.school_id != context.school_id
            or audit_intent.actor_id != context.actor_id
            or camera.camera_id != audit_intent.resource_id
            or camera.zone_id != audit_intent.zone_id
            or audit_intent.resource_type != "camera"
        ):
            raise CameraRegistryError("CAMERA_AUTHORITY_DENIED")
        try:
            with self._engine.begin() as connection:
                _lock_idempotency(connection, camera.school_id, audit_intent.idempotency_key)
                existing = _existing_outcome(
                    connection,
                    camera.school_id,
                    audit_intent.idempotency_key,
                    audit_intent.request_fingerprint,
                )
                if existing is not None:
                    return existing
                zone = _locked_zone(connection, camera.school_id, camera.zone_id)
                context.authorize_zone(zone.zone_id, camera.purpose_codes)
                authorize_zone_compatibility(zone, camera.purpose_codes)
                connection.execute(sa.insert(cameras).values(**_camera_values(camera)))
                connection.execute(
                    sa.insert(camera_audit_outbox).values(**_intent_values(audit_intent))
                )
                return RegistryChangeOutcome(camera, audit_intent, duplicate=False)
        except CameraRegistryError:
            raise
        except IntegrityError as exc:
            raise CameraRegistryError(_integrity_error_code(exc, "CAMERA_ALREADY_EXISTS")) from None
        except SQLAlchemyError:
            raise CameraRegistryError("CAMERA_UNAVAILABLE") from None

    def change_camera(
        self,
        request: CameraChangeRequest,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        _validate_context(request, context)
        try:
            with self._engine.begin() as connection:
                _lock_idempotency(
                    connection, request.metadata.school_id, request.metadata.idempotency_key
                )
                existing = _existing_outcome(
                    connection,
                    request.metadata.school_id,
                    request.metadata.idempotency_key,
                    request.metadata.request_fingerprint,
                )
                if existing is not None:
                    return existing
                current = _locked_camera(connection, context.school_id, request.camera_id)
                context.authorize_zone(current.zone_id, current.purpose_codes)
                if current.row_version != request.expected_version:
                    raise CameraRegistryError("CAMERA_VERSION_CONFLICT")
                if request.operation is CameraChangeOperation.UPDATE:
                    target_zone_id = current.zone_id if request.zone_id is None else request.zone_id
                    target_purposes = (
                        current.purpose_codes
                        if request.purpose_codes is None
                        else request.purpose_codes
                    )
                    context.authorize_zone(target_zone_id, target_purposes)
                    target_zone = _locked_zone(connection, context.school_id, target_zone_id)
                    authorize_zone_compatibility(target_zone, target_purposes)
                    target_name = (
                        current.display_name
                        if request.display_name is None
                        else request.display_name
                    )
                    target_config = (
                        current.config_version
                        if request.config_version is None
                        else request.config_version
                    )
                    if (
                        target_zone_id == current.zone_id
                        and target_name == current.display_name
                        and target_purposes == current.purpose_codes
                        and target_config == current.config_version
                    ):
                        raise CameraRegistryError("CAMERA_NO_CHANGE")
                    updated = update_camera(
                        current,
                        zone_id=request.zone_id,
                        display_name=request.display_name,
                        purpose_codes=request.purpose_codes,
                        config_version=request.config_version,
                        changed_at=request.metadata.changed_at,
                    )
                    fields: list[str] = []
                    if request.zone_id is not None:
                        fields.append("zone")
                    if request.display_name is not None:
                        fields.append("metadata")
                    if request.purpose_codes is not None:
                        fields.append("purpose")
                    if request.config_version is not None:
                        fields.append("config")
                    changed_fields = tuple(fields)
                elif request.operation is CameraChangeOperation.MAP:
                    if (
                        current.source_id == request.source_id
                        and current.task_id == request.task_id
                        and current.mapping_purpose_code == request.mapping_purpose_code
                        and current.credential_ref == request.credential_ref
                        and current.schedule_version == request.schedule_version
                        and current.config_version == request.config_version
                    ):
                        raise CameraRegistryError("CAMERA_NO_CHANGE")
                    updated = map_camera(current, request)
                    context.authorize_zone(updated.zone_id, updated.purpose_codes)
                    connection.execute(
                        sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:mapping, 2))"),
                        {"mapping": f"{context.school_id}:{updated.source_id}:{updated.task_id}"},
                    )
                    mapped_camera = connection.scalar(
                        sa.select(cameras.c.camera_id).where(
                            cameras.c.school_id == context.school_id,
                            cameras.c.source_id == updated.source_id,
                            cameras.c.task_id == updated.task_id,
                            cameras.c.camera_id != current.camera_id,
                        )
                    )
                    if mapped_camera is not None:
                        raise CameraRegistryError("CAMERA_MAPPING_CONFLICT")
                    changed_fields = (
                        "ansvis_source",
                        "config",
                        "purpose",
                        "schedule",
                        "task",
                    )
                else:
                    updated = deactivate_camera(current, changed_at=request.metadata.changed_at)
                    changed_fields = ("status",)
                result = connection.execute(
                    sa.update(cameras)
                    .where(
                        cameras.c.school_id == context.school_id,
                        cameras.c.camera_id == current.camera_id,
                        cameras.c.row_version == request.expected_version,
                    )
                    .values(**_camera_values(updated))
                )
                if result.rowcount != 1:
                    raise CameraRegistryError("CAMERA_VERSION_CONFLICT")
                intent = _change_intent(request, current, updated, changed_fields)
                connection.execute(sa.insert(camera_audit_outbox).values(**_intent_values(intent)))
                return RegistryChangeOutcome(updated, intent, duplicate=False)
        except CameraRegistryError:
            raise
        except IntegrityError as exc:
            raise CameraRegistryError(
                _integrity_error_code(exc, "CAMERA_MAPPING_CONFLICT")
            ) from None
        except SQLAlchemyError:
            raise CameraRegistryError("CAMERA_UNAVAILABLE") from None

    def get_zone(self, zone_id: UUID, school_id: UUID) -> Zone | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(zones).where(
                            zones.c.school_id == school_id,
                            zones.c.zone_id == zone_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return None if row is None else _zone(row)
        except CameraRegistryError:
            raise
        except SQLAlchemyError:
            raise CameraRegistryError("CAMERA_UNAVAILABLE") from None

    def get_camera(self, camera_id: UUID, school_id: UUID) -> Camera | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(cameras).where(
                            cameras.c.school_id == school_id,
                            cameras.c.camera_id == camera_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return None if row is None else _camera(row)
        except CameraRegistryError:
            raise
        except SQLAlchemyError:
            raise CameraRegistryError("CAMERA_UNAVAILABLE") from None
