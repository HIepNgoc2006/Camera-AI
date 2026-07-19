from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from camera_registry_service.application.service import CameraRegistryApplicationService
from camera_registry_service.domain.errors import CameraRegistryError
from camera_registry_service.domain.models import Camera, TrustedRegistryContext, Zone
from camera_registry_service.infrastructure.repository import SqlAlchemyCameraRegistryRepository
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000501")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000502")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000503")
TASK_ID = UUID("00000000-0000-4000-8000-000000000504")

EXPECTED_TABLES = {"camera_audit_outbox", "cameras", "zones"}
EXPECTED_CAMERA_COLUMNS = {
    "camera_id",
    "school_id",
    "zone_id",
    "code",
    "display_name",
    "purpose_codes",
    "source_id",
    "task_id",
    "mapping_purpose_code",
    "credential_ref",
    "schedule_version",
    "config_version",
    "status",
    "last_seen_at",
    "deactivated_at",
    "created_at",
    "updated_at",
    "row_version",
}


class SequenceIdentifierFactory:
    def __init__(self, values: list[UUID]) -> None:
        self._values = iter(values)

    def __call__(self) -> UUID:
        return next(self._values)


def _test_database_uri() -> str:
    raw_uri = os.environ.get("CAMERA_DATABASE_URI", "").strip()
    if not raw_uri:
        pytest.skip("CAMERA_DATABASE_URI is required for isolated camera integration verification")
    url = make_url(raw_uri)
    database_name = (url.database or "").casefold()
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database_name.endswith("_test")
    ):
        pytest.fail("camera integration test requires an isolated loopback non-5432 *_test DB")
    return raw_uri


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def _context(zone_ids: frozenset[UUID]) -> TrustedRegistryContext:
    return TrustedRegistryContext(
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        allowed_zone_ids=zone_ids,
        allowed_purpose_codes=frozenset({"student_attendance", "student_uniform"}),
        assignment_verified=True,
        can_manage_zones=True,
        can_manage_cameras=True,
    )


def _mutation(suffix: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "request_id": f"req_{suffix}",
        "idempotency_key": f"idem_{suffix}",
        "policy_version": "camera_policy_v1",
    }


def _camera_payload(zone_id: UUID, code: str, suffix: str) -> dict[str, object]:
    return {
        **_mutation(suffix),
        "zone_id": str(zone_id),
        "code": code,
        "display_name": f"Synthetic {code}",
        "purpose_codes": ["student_attendance"],
        "config_version": "camera_cfg_v1",
    }


def _assert_inventory(engine: Engine) -> None:
    inspector = inspect(engine)
    assert inspector.has_schema("camera")
    assert set(inspector.get_table_names(schema="camera")) == EXPECTED_TABLES
    assert {
        column["name"] for column in inspector.get_columns("cameras", schema="camera")
    } == EXPECTED_CAMERA_COLUMNS
    foreign_keys = inspector.get_foreign_keys("cameras", schema="camera")
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["referred_schema"] == "camera"
    assert foreign_keys[0]["referred_table"] == "zones"
    with engine.connect() as connection:
        triggers = set(
            connection.scalars(
                sa.text(
                    "SELECT tgname FROM pg_trigger WHERE tgrelid IN "
                    "('camera.zones'::regclass, 'camera.cameras'::regclass) "
                    "AND NOT tgisinternal"
                )
            )
        )
    assert triggers == {
        "cameras_reject_delete",
        "cameras_reject_truncate",
        "zones_reject_delete",
        "zones_reject_truncate",
    }


def test_camera_registry_migration_idempotency_mapping_concurrency_and_audit() -> None:
    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    try:
        command.downgrade(config, "base")
        assert inspect(engine).has_schema("camera") is False
        command.upgrade(config, "head")
        upgraded = True
        _assert_inventory(engine)

        repository = SqlAlchemyCameraRegistryRepository(engine)
        service = CameraRegistryApplicationService(repository, clock=lambda: NOW)
        bootstrap_context = _context(frozenset())
        zone_payload = {
            **_mutation("1111111111111111"),
            "code": "gate_a",
            "name": "Synthetic Gate A",
            "zone_type": "gate",
            "sensitivity": "high",
            "purpose_codes": ["student_attendance", "student_uniform"],
        }
        zone_created = service.register_zone(zone_payload, bootstrap_context)
        zone_duplicate = service.register_zone(zone_payload, bootstrap_context)
        assert isinstance(zone_created.resource, Zone)
        assert zone_duplicate.duplicate is True
        assert zone_duplicate.resource.zone_id == zone_created.resource.zone_id

        zone_conflict = dict(zone_payload)
        zone_conflict["name"] = "Conflicting Synthetic Gate"
        with pytest.raises(CameraRegistryError, match="CAMERA_DUPLICATE_CONFLICT"):
            service.register_zone(zone_conflict, bootstrap_context)

        zone_id = zone_created.resource.zone_id
        context = _context(frozenset({zone_id}))

        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO camera.cameras "
                    "(camera_id, school_id, zone_id, code, display_name, purpose_codes, "
                    "config_version) VALUES "
                    "(:camera_id, :school_id, :zone_id, 'cross_tenant_camera', "
                    "'Synthetic Cross Tenant Camera', ARRAY['student_attendance'], 'camera_cfg_v1')"
                ),
                {
                    "camera_id": UUID("00000000-0000-4000-8000-000000000507"),
                    "school_id": UUID("00000000-0000-4000-8000-000000000508"),
                    "zone_id": zone_id,
                },
            )

        atomic_camera_id = UUID("00000000-0000-4000-8000-000000000505")
        atomicity_service = CameraRegistryApplicationService(
            repository,
            clock=lambda: NOW,
            identifier_factory=SequenceIdentifierFactory(
                [
                    atomic_camera_id,
                    zone_created.audit_intent.source_event_id,
                    UUID("00000000-0000-4000-8000-000000000506"),
                ]
            ),
        )
        with pytest.raises(CameraRegistryError, match="CAMERA_DUPLICATE_CONFLICT"):
            atomicity_service.register_camera(
                _camera_payload(zone_id, "camera_atomic", "1212121212121212"),
                context,
            )
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT count(*) FROM camera.cameras")) == 0

        first_payload = _camera_payload(zone_id, "camera_a", "2222222222222222")
        first_created = service.register_camera(first_payload, context)
        first_duplicate = service.register_camera(first_payload, context)
        first_camera = first_created.resource
        first_retry_camera = first_duplicate.resource
        assert isinstance(first_camera, Camera)
        assert isinstance(first_retry_camera, Camera)
        assert first_duplicate.duplicate is True
        assert first_retry_camera.camera_id == first_camera.camera_id

        mapped = service.map_camera(
            {
                **_mutation("3333333333333333"),
                "camera_id": str(first_camera.camera_id),
                "expected_version": 1,
                "source_id": str(SOURCE_ID),
                "task_id": str(TASK_ID),
                "mapping_purpose_code": "student_attendance",
                "credential_ref": "sec_v1_" + "C" * 32,
                "schedule_version": "school_schedule_v1",
                "config_version": "camera_cfg_v2",
            },
            context,
        )
        mapping_duplicate = service.map_camera(
            {
                **_mutation("3333333333333333"),
                "camera_id": str(first_camera.camera_id),
                "expected_version": 1,
                "source_id": str(SOURCE_ID),
                "task_id": str(TASK_ID),
                "mapping_purpose_code": "student_attendance",
                "credential_ref": "sec_v1_" + "C" * 32,
                "schedule_version": "school_schedule_v1",
                "config_version": "camera_cfg_v2",
            },
            context,
        )
        assert mapped.resource.row_version == 2
        assert mapping_duplicate.duplicate is True

        second_created = service.register_camera(
            _camera_payload(zone_id, "camera_b", "4444444444444444"), context
        )
        second_camera = second_created.resource
        assert isinstance(second_camera, Camera)
        with pytest.raises(CameraRegistryError, match="CAMERA_MAPPING_CONFLICT"):
            service.map_camera(
                {
                    **_mutation("5555555555555555"),
                    "camera_id": str(second_camera.camera_id),
                    "expected_version": 1,
                    "source_id": str(SOURCE_ID),
                    "task_id": str(TASK_ID),
                    "mapping_purpose_code": "student_attendance",
                    "credential_ref": None,
                    "schedule_version": "school_schedule_v1",
                    "config_version": "camera_cfg_v2",
                },
                context,
            )

        competing = (
            {
                **_mutation("6666666666666666"),
                "camera_id": str(first_camera.camera_id),
                "expected_version": 2,
                "display_name": "Synthetic Camera A Revision One",
            },
            {
                **_mutation("7777777777777777"),
                "camera_id": str(first_camera.camera_id),
                "expected_version": 2,
                "display_name": "Synthetic Camera A Revision Two",
            },
        )

        def run_update(payload: dict[str, object]) -> int | str:
            try:
                return service.update_camera(payload, context).resource.row_version
            except CameraRegistryError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrency_results = list(executor.map(run_update, competing))
        assert sum(result == "CAMERA_VERSION_CONFLICT" for result in concurrency_results) == 1
        assert sum(result == 3 for result in concurrency_results) == 1

        current_first = service.get_camera(first_camera.camera_id, context)
        disabled_first = service.deactivate_camera(
            {
                **_mutation("8888888888888888"),
                "camera_id": str(current_first.camera_id),
                "expected_version": current_first.row_version,
                "reason_code": "REGISTRY_DEACTIVATION",
            },
            context,
        )
        assert disabled_first.resource.status == "disabled"

        with pytest.raises(CameraRegistryError, match="CAMERA_ZONE_IN_USE"):
            service.deactivate_zone(
                {
                    **_mutation("9999999999999999"),
                    "zone_id": str(zone_id),
                    "expected_version": 1,
                    "reason_code": "REGISTRY_DEACTIVATION",
                },
                context,
            )

        disabled_second = service.deactivate_camera(
            {
                **_mutation("aaaaaaaaaaaaaaaa"),
                "camera_id": str(second_camera.camera_id),
                "expected_version": 1,
                "reason_code": "REGISTRY_DEACTIVATION",
            },
            context,
        )
        assert disabled_second.resource.status == "disabled"
        inactive_zone = service.deactivate_zone(
            {
                **_mutation("bbbbbbbbbbbbbbbb"),
                "zone_id": str(zone_id),
                "expected_version": 1,
                "reason_code": "REGISTRY_DEACTIVATION",
            },
            context,
        )
        assert inactive_zone.resource.status == "inactive"

        with engine.connect() as connection:
            counts = (
                connection.execute(
                    sa.text(
                        "SELECT "
                        "(SELECT count(*) FROM camera.zones) AS zones, "
                        "(SELECT count(*) FROM camera.cameras) AS cameras, "
                        "(SELECT count(*) FROM camera.camera_audit_outbox) AS intents, "
                        "(SELECT count(*) FROM camera.camera_audit_outbox "
                        " WHERE delivery_status = 'pending') AS pending"
                    )
                )
                .mappings()
                .one()
            )
            stored_reference = connection.scalar(
                sa.text("SELECT credential_ref FROM camera.cameras WHERE camera_id = :camera_id"),
                {"camera_id": first_camera.camera_id},
            )
        assert counts == {"zones": 1, "cameras": 2, "intents": 8, "pending": 8}
        assert stored_reference == "sec_v1_" + "C" * 32

        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text("DELETE FROM camera.cameras WHERE camera_id = :camera_id"),
                {"camera_id": first_camera.camera_id},
            )

        command.downgrade(config, "base")
        upgraded = False
        assert inspect(engine).has_schema("camera") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
