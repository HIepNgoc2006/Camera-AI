from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260728_0001_create_notification_baseline.py"
)


def test_migration_owns_only_notification_schema_and_models_required_state() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'SCHEMA = "notification"' in source
    for table in (
        "notification_intents",
        "recipient_deliveries",
        "delivery_attempts",
        "recipient_endpoints",
        "notification_cancellations",
        "audit_outbox",
    ):
        assert f'"{table}"' in source
    for cross_schema in ("identity.", "school.", "privacy.", "events.", "audit.", "evidence."):
        assert re.search(rf"(?<![a-z_]){re.escape(cross_schema)}", source) is None


def test_migration_enforces_encryption_minimization_retry_and_append_only_history() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "encv1_check_constraint",
        "endpoint_lookup_digest",
        "ck_notification_deliveries_content_allowlist",
        "ck_notification_deliveries_no_remote_resource",
        "attempt_count BETWEEN 0 AND 5",
        "uq_notification_intents_idempotency",
        "reject_append_only_change",
        "REVOKE UPDATE, DELETE, TRUNCATE",
        "notification_privacy_policy_v1",
        "payload ?| ARRAY",
    ):
        assert marker in source
