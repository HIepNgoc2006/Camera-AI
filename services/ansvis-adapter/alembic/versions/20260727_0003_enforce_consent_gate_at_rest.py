"""Enforce the Issue #139 consent gate at rest.

Face and emotion events can no longer be stored as ``not_evaluated``: the CHECK
added here forbids it, the receipts enum gains the ``deferred`` outcome used
when the consent gate is unreachable, the outbox gains the terminal ``refused``
state the fan-out guard writes, and every event row carries the consent policy
version its decision was made under.

Disposition of pre-existing rows (development/synthetic data only — no
production deployment exists): face/emotion rows still holding the legacy
``not_evaluated`` status are retroactively set to ``blocked`` with policy
version ``pre_gate_disposition_v1``; they never had business projections and
their pending outbox messages are refused by the runtime guard, never
published. All other rows are backfilled with the same disposition version
marker. The append-only trigger is disabled only inside this migration
transaction for exactly that statement.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0003"
down_revision: str | Sequence[str] | None = "20260726_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "events"
BIOMETRIC_EVENT_TYPES = (
    "attendance.face.observed",
    "timekeeping.face.observed",
    "insight.emotion.observed",
)
DISPOSITION_POLICY_VERSION = "pre_gate_disposition_v1"
RECEIPT_RESULTS = ("accepted", "duplicate", "rejected", "deferred")
LEGACY_RECEIPT_RESULTS = ("accepted", "duplicate", "rejected")
PUBLISH_STATES = ("pending", "published", "failed", "refused")
LEGACY_PUBLISH_STATES = ("pending", "published", "failed")
METADATA_KEYS = ("schema_version", "status", "rule_code", "detection_count")
OUTBOX_KEYS = (
    "schema_version",
    "normalized_event_id",
    "school_id",
    "source_id",
    "camera_id",
    "task_id",
    "event_type",
    "event_time",
    "correlation_id",
    "model_version",
    "config_version",
    "consent_gate_status",
    "consent_policy_version",
    "confidence",
    "metadata",
)
OUTBOX_REQUIRED_KEYS = tuple(key for key in OUTBOX_KEYS if key != "confidence")
LEGACY_OUTBOX_KEYS = tuple(key for key in OUTBOX_KEYS if key != "consent_policy_version")
LEGACY_OUTBOX_REQUIRED_KEYS = tuple(key for key in LEGACY_OUTBOX_KEYS if key != "confidence")


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _text_array(values: Iterable[str]) -> str:
    return f"ARRAY[{_quoted(values)}]::text[]"


def _outbox_payload_allowlist(keys: Iterable[str], required: Iterable[str]) -> str:
    return (
        "jsonb_typeof(payload) = 'object' AND "
        f"payload ?& {_text_array(required)} AND "
        "payload->>'schema_version' = 'normalized_outbox_v1' AND "
        f"payload - {_text_array(keys)} = '{{}}'::jsonb AND "
        "jsonb_typeof(payload->'metadata') = 'object' AND "
        "payload->'metadata'->>'schema_version' = 'event_metadata_v1' AND "
        f"(payload->'metadata') - {_text_array(METADATA_KEYS)} = '{{}}'::jsonb"
    )


def upgrade() -> None:
    # Receipts: allow the durable 'deferred' outcome used while the consent
    # gate is unreachable; deferred receipts carry the stable error code.
    op.drop_constraint("ck_events_receipts_result", "ingestion_receipts", schema=SCHEMA)
    op.drop_constraint("ck_events_receipts_error_state", "ingestion_receipts", schema=SCHEMA)
    op.create_check_constraint(
        "ck_events_receipts_result",
        "ingestion_receipts",
        f"result IN ({_quoted(RECEIPT_RESULTS)})",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_events_receipts_error_state",
        "ingestion_receipts",
        "((result IN ('rejected', 'deferred')) = (error_code IS NOT NULL))",
        schema=SCHEMA,
    )

    # Normalized events: persist the consent policy version and forbid the
    # legacy 'not_evaluated' status at rest for biometric event types.
    op.add_column(
        "normalized_events",
        sa.Column("consent_policy_version", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "ALTER TABLE events.normalized_events DISABLE TRIGGER normalized_events_reject_mutation"
        )
    )
    op.execute(
        sa.text(
            "UPDATE events.normalized_events "
            "SET consent_gate_status = 'blocked', "
            f"consent_policy_version = '{DISPOSITION_POLICY_VERSION}' "
            f"WHERE event_type IN ({_quoted(BIOMETRIC_EVENT_TYPES)}) "
            "AND consent_gate_status = 'not_evaluated'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE events.normalized_events "
            f"SET consent_policy_version = '{DISPOSITION_POLICY_VERSION}' "
            "WHERE consent_policy_version IS NULL"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE events.normalized_events ENABLE TRIGGER normalized_events_reject_mutation"
        )
    )
    op.alter_column(
        "normalized_events",
        "consent_policy_version",
        nullable=False,
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_events_normalized_consent_policy_version",
        "normalized_events",
        "consent_policy_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_events_normalized_consent_at_rest",
        "normalized_events",
        f"NOT (event_type IN ({_quoted(BIOMETRIC_EVENT_TYPES)}) "
        "AND consent_gate_status = 'not_evaluated')",
        schema=SCHEMA,
    )

    # Outbox: payloads carry the consent policy version, and the fan-out guard
    # gets its terminal 'refused' state. Pre-existing payloads receive the
    # disposition marker; stale biometric payloads keep their legacy status and
    # are refused by the guard at dispatch instead of being published.
    op.execute(
        sa.text(
            "UPDATE events.outbox_messages "
            "SET payload = jsonb_set(payload, '{consent_policy_version}', "
            f"'\"{DISPOSITION_POLICY_VERSION}\"'::jsonb, true) "
            "WHERE NOT payload ? 'consent_policy_version'"
        )
    )
    op.drop_constraint("ck_events_outbox_payload_allowlist", "outbox_messages", schema=SCHEMA)
    op.create_check_constraint(
        "ck_events_outbox_payload_allowlist",
        "outbox_messages",
        _outbox_payload_allowlist(OUTBOX_KEYS, OUTBOX_REQUIRED_KEYS),
        schema=SCHEMA,
    )
    op.drop_constraint("ck_events_outbox_status", "outbox_messages", schema=SCHEMA)
    op.create_check_constraint(
        "ck_events_outbox_status",
        "outbox_messages",
        f"publish_status IN ({_quoted(PUBLISH_STATES)})",
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Synthetic-data disposition in reverse: refused messages become terminal
    # 'failed' rows (the legacy bound requires attempt_count = 5), deferred
    # receipts collapse to 'rejected', and the payload key is stripped.
    op.execute(
        sa.text(
            "UPDATE events.outbox_messages "
            "SET publish_status = 'failed', attempt_count = 5 "
            "WHERE publish_status = 'refused'"
        )
    )
    op.drop_constraint("ck_events_outbox_status", "outbox_messages", schema=SCHEMA)
    op.create_check_constraint(
        "ck_events_outbox_status",
        "outbox_messages",
        f"publish_status IN ({_quoted(LEGACY_PUBLISH_STATES)})",
        schema=SCHEMA,
    )
    # Drop the strict allowlist BEFORE stripping the key it requires; the
    # legacy allowlist is recreated only after every payload is legacy-shaped.
    op.drop_constraint("ck_events_outbox_payload_allowlist", "outbox_messages", schema=SCHEMA)
    op.execute(
        sa.text(
            "UPDATE events.outbox_messages "
            "SET payload = payload - 'consent_policy_version' "
            "WHERE payload ? 'consent_policy_version'"
        )
    )
    op.create_check_constraint(
        "ck_events_outbox_payload_allowlist",
        "outbox_messages",
        _outbox_payload_allowlist(LEGACY_OUTBOX_KEYS, LEGACY_OUTBOX_REQUIRED_KEYS),
        schema=SCHEMA,
    )

    op.drop_constraint("ck_events_normalized_consent_at_rest", "normalized_events", schema=SCHEMA)
    op.drop_constraint(
        "ck_events_normalized_consent_policy_version", "normalized_events", schema=SCHEMA
    )
    op.drop_column("normalized_events", "consent_policy_version", schema=SCHEMA)

    op.execute(
        sa.text(
            "ALTER TABLE events.ingestion_receipts "
            "DISABLE TRIGGER ingestion_receipts_reject_mutation"
        )
    )
    op.execute(
        sa.text(
            "UPDATE events.ingestion_receipts SET result = 'rejected' WHERE result = 'deferred'"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE events.ingestion_receipts "
            "ENABLE TRIGGER ingestion_receipts_reject_mutation"
        )
    )
    op.drop_constraint("ck_events_receipts_error_state", "ingestion_receipts", schema=SCHEMA)
    op.drop_constraint("ck_events_receipts_result", "ingestion_receipts", schema=SCHEMA)
    op.create_check_constraint(
        "ck_events_receipts_result",
        "ingestion_receipts",
        f"result IN ({_quoted(LEGACY_RECEIPT_RESULTS)})",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_events_receipts_error_state",
        "ingestion_receipts",
        "((result = 'rejected') = (error_code IS NOT NULL))",
        schema=SCHEMA,
    )
