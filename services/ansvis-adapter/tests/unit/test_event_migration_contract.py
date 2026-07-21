from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260721_0001_create_event_ingestion_baseline.py"
)


def test_migration_owns_only_the_approved_event_ingestion_objects() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'SCHEMA = "events"' in source
    for table in (
        "ingestion_receipts",
        "normalized_events",
        "event_detections",
        "processing_attempts",
        "outbox_messages",
    ):
        assert f'"{table}"' in source
    for cross_schema in (
        "identity.",
        "school.",
        "privacy.",
        "camera.cameras",
        "camera.zones",
        "integration.",
        "attendance.attendance_",
        "evidence.",
        "audit.",
    ):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_contains_concurrency_retention_and_append_only_guards() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "uq_events_receipts_source_key",
        "fk_events_normalized_receipt_scope",
        "uq_events_normalized_receipt",
        "uq_events_detections_event_index",
        "uq_events_attempts_event_consumer_number",
        "uq_events_outbox_event_topic_contract",
        "retention_until > recorded_at",
        "attempt_count >= 0 AND attempt_count <= 5",
        "reject_event_mutation",
        "BEFORE UPDATE OR DELETE OR TRUNCATE",
        "REVOKE DELETE, TRUNCATE",
    ):
        assert marker in source


def test_migration_json_contracts_are_allowlisted_and_forbid_sensitive_shapes() -> None:
    source = MIGRATION.read_text(encoding="utf-8").casefold()
    for marker in (
        "event_metadata_v1",
        "detection_attributes_v1",
        "normalized_outbox_v1",
        "payload - ",
        "sanitized_metadata - ",
        "attributes - ",
    ):
        assert marker in source
    for forbidden in (
        "raw_payload",
        "face_image",
        "face_embedding",
        "media_url",
        "signed_url",
        "base64",
        "rtsp_url",
        "password",
        "authorization",
        "subject_external_id",
    ):
        assert forbidden not in source
