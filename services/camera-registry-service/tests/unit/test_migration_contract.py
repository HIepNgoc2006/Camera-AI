from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260719_0001_create_camera_registry_baseline.py"
)


def test_migration_owns_only_approved_camera_objects() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'SCHEMA = "camera"' in source
    for table in ("zones", "cameras", "camera_audit_outbox"):
        assert f'"{table}"' in source
    for cross_schema in (
        "school.",
        "identity.",
        "privacy.",
        "audit.",
        "integration.",
        "events.",
        "evidence.",
    ):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_contains_mapping_concurrency_and_minimization_guards() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "row_version",
        "fk_camera_cameras_school_zone",
        "uq_camera_cameras_primary_mapping",
        "uq_camera_zones_school_zone",
        "uq_camera_outbox_idempotency",
        "request_fingerprint",
        "credential_ref ~ '^sec_v1_",
        "reject_registry_delete",
        "camera_audit_outbox",
    ):
        assert marker in source
    for forbidden in (
        "camera_address",
        "face_image",
        "face_embedding",
        "raw_payload",
        "signed_url",
        "base64",
        "rtsp_url",
        "password_hash",
    ):
        assert forbidden not in source.casefold()
