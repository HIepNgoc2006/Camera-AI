from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260721_0001_create_event_ingestion_baseline.py"
)
CONSENT_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260727_0003_enforce_consent_gate_at_rest.py"
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


def test_consent_migration_enforces_the_gate_at_rest_without_cross_schema_reads() -> None:
    source = CONSENT_MIGRATION.read_text(encoding="utf-8")

    for marker in (
        "ck_events_normalized_consent_at_rest",
        "ck_events_normalized_consent_policy_version",
        "consent_policy_version",
        '"attendance.face.observed"',
        '"timekeeping.face.observed"',
        '"insight.emotion.observed"',
        "AND consent_gate_status = 'not_evaluated')",
        '"pending", "published", "failed", "refused"',
        '"accepted", "duplicate", "rejected", "deferred"',
        "pre_gate_disposition_v1",
        "DISABLE TRIGGER normalized_events_reject_mutation",
        "ENABLE TRIGGER normalized_events_reject_mutation",
    ):
        assert marker in source
    for cross_schema in (
        "identity.",
        "school.",
        "privacy.",
        "camera.cameras",
        "integration.",
        "attendance.attendance_",
        "evidence.",
        "audit.audit_",
    ):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None
    for forbidden in ("raw_payload", "face_image", "base64", "subject_external_id"):
        assert forbidden not in source.casefold()


def test_consent_migration_downgrade_removes_strict_payload_check_before_rewrite() -> None:
    source = CONSENT_MIGRATION.read_text(encoding="utf-8")
    downgrade = source[source.index("def downgrade() -> None:") :]
    drop_allowlist = downgrade.index('op.drop_constraint("ck_events_outbox_payload_allowlist"')
    strip_policy_version = downgrade.index("\"SET payload = payload - 'consent_policy_version' \"")
    recreate_allowlist = downgrade.index(
        'op.create_check_constraint(\n        "ck_events_outbox_payload_allowlist"'
    )

    assert drop_allowlist < strip_policy_version < recreate_allowlist
