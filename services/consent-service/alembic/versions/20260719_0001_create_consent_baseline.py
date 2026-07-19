"""Create the fail-closed purpose and consent baseline.

Revision ID: 20260719_0001
Revises:
Create Date: 2026-07-19 00:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "privacy"
DATA_CATEGORIES = (
    "attendance",
    "biometric",
    "camera_event",
    "emotion",
    "evidence",
    "student_profile",
    "timekeeping",
    "violation",
)
CONSENT_STATUSES = ("pending", "granted", "denied", "withdrawn", "expired", "restricted")
EVENT_TYPES = ("requested", "granted", "denied", "withdrawn", "expired", "restricted")
AUDIT_ACTIONS = (
    "CONSENT_REQUESTED",
    "CONSENT_GRANTED",
    "CONSENT_DENIED",
    "CONSENT_WITHDRAWN",
    "CONSENT_EXPIRED",
    "CONSENT_RESTRICTED",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_purposes() -> None:
    op.create_table(
        "purposes",
        sa.Column(
            "purpose_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("data_categories", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column(
            "requires_biometric_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_.:-]{0,63}$'", name="ck_purposes_code"),
        sa.CheckConstraint(
            "char_length(description) BETWEEN 1 AND 512", name="ck_purposes_description"
        ),
        sa.CheckConstraint(
            f"cardinality(data_categories) BETWEEN 1 AND 32 AND "
            f"data_categories <@ ARRAY[{_quoted(DATA_CATEGORIES)}]::text[]",
            name="ck_purposes_data_categories",
        ),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_purposes_status"),
        sa.CheckConstraint("version > 0", name="ck_purposes_version"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_purposes_validity"
        ),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_purposes_business_version "
            "ON privacy.purposes (school_id, code, version) NULLS NOT DISTINCT"
        )
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_purposes_active_code "
            "ON privacy.purposes (school_id, code) NULLS NOT DISTINCT WHERE status = 'active'"
        )
    )
    op.create_index(
        "ix_purposes_school_status_validity",
        "purposes",
        ["school_id", "status", "valid_from", "valid_to"],
        schema=SCHEMA,
    )


def _create_consents() -> None:
    op.create_table(
        "consents",
        sa.Column(
            "consent_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authority_type", sa.Text(), nullable=False),
        sa.Column("authority_ref", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("scope_codes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restricted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("row_version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("subject_type IN ('student', 'staff')", name="ck_consents_subject_type"),
        sa.CheckConstraint(
            "authority_type IN ('self', 'guardian', 'legal_basis')",
            name="ck_consents_authority_type",
        ),
        sa.CheckConstraint(f"status IN ({_quoted(CONSENT_STATUSES)})", name="ck_consents_status"),
        sa.CheckConstraint(
            f"cardinality(scope_codes) BETWEEN 1 AND 32 AND "
            f"scope_codes <@ ARRAY[{_quoted(DATA_CATEGORIES)}]::text[]",
            name="ck_consents_scope_codes",
        ),
        sa.CheckConstraint(
            "policy_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_consents_policy_version",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to > valid_from)",
            name="ck_consents_validity",
        ),
        sa.CheckConstraint(
            "status <> 'granted' OR valid_from IS NOT NULL",
            name="ck_consents_granted_valid_from",
        ),
        sa.CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)",
            name="ck_consents_withdrawal_state",
        ),
        sa.CheckConstraint(
            "(status = 'restricted') = (restricted_at IS NOT NULL)",
            name="ck_consents_restriction_state",
        ),
        sa.CheckConstraint("row_version > 0", name="ck_consents_row_version"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_consents_timestamps"),
        sa.ForeignKeyConstraint(
            ["purpose_id"],
            ["privacy.purposes.purpose_id"],
            name="fk_consents_purpose_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "school_id",
            "subject_type",
            "subject_id",
            "purpose_id",
            name="uq_consents_current_subject_purpose",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_consents_subject_status_validity",
        "consents",
        ["school_id", "subject_type", "subject_id", "status", "valid_to"],
        schema=SCHEMA,
    )


def _create_consent_events() -> None:
    op.create_table(
        "consent_events",
        sa.Column(
            "consent_event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", postgresql.BYTEA(), nullable=False),
        sa.Column("resulting_version", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"event_type IN ({_quoted(EVENT_TYPES)})", name="ck_consent_events_type"
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{1,63}$'",
            name="ck_consent_events_reason_code",
        ),
        sa.CheckConstraint(
            "event_type IN ('requested', 'granted') OR reason_code IS NOT NULL",
            name="ck_consent_events_reason_required",
        ),
        sa.CheckConstraint(
            "request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'",
            name="ck_consent_events_request_id",
        ),
        sa.CheckConstraint(
            "evidence_ref IS NULL OR evidence_ref ~ "
            "'^(authority_record|legal_basis_record):"
            "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'",
            name="ck_consent_events_evidence_ref",
        ),
        sa.CheckConstraint(
            "idempotency_key ~ '^idem_[A-Za-z0-9_-]{8,120}$'",
            name="ck_consent_events_idempotency_key",
        ),
        sa.CheckConstraint(
            "octet_length(request_fingerprint) = 32",
            name="ck_consent_events_request_fingerprint",
        ),
        sa.CheckConstraint("resulting_version > 0", name="ck_consent_events_version"),
        sa.ForeignKeyConstraint(
            ["consent_id"],
            ["privacy.consents.consent_id"],
            name="fk_consent_events_consent_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("school_id", "idempotency_key", name="uq_consent_events_idempotency"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_consent_events_consent_occurred",
        "consent_events",
        ["consent_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_consent_events_actor_occurred",
        "consent_events",
        ["actor_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )


def _create_audit_outbox() -> None:
    op.create_table(
        "consent_audit_outbox",
        sa.Column(
            "audit_intent_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("consent_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_schema_version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("source_service", sa.Text(), nullable=False, server_default="consent-service"),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("purpose_code", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False, server_default="consent"),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False, server_default="success"),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("state_before", sa.Text(), nullable=True),
        sa.Column("state_after", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("event_schema_version = 1", name="ck_consent_outbox_schema_version"),
        sa.CheckConstraint(
            "source_service = 'consent-service'", name="ck_consent_outbox_source_service"
        ),
        sa.CheckConstraint(
            f"action IN ({_quoted(AUDIT_ACTIONS)})", name="ck_consent_outbox_action"
        ),
        sa.CheckConstraint(
            "purpose_code ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_consent_outbox_purpose_code",
        ),
        sa.CheckConstraint("resource_type = 'consent'", name="ck_consent_outbox_resource_type"),
        sa.CheckConstraint(
            "result IN ('success', 'denied') AND "
            "((action = 'CONSENT_DENIED') = (result = 'denied'))",
            name="ck_consent_outbox_result",
        ),
        sa.CheckConstraint(
            "request_id ~ '^req_[A-Za-z0-9_-]{8,120}$'",
            name="ck_consent_outbox_request_id",
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{1,63}$'",
            name="ck_consent_outbox_reason_code",
        ),
        sa.CheckConstraint(
            f"state_before IS NULL OR state_before IN ({_quoted(CONSENT_STATUSES)})",
            name="ck_consent_outbox_state_before",
        ),
        sa.CheckConstraint(
            f"state_after IN ({_quoted(CONSENT_STATUSES)})",
            name="ck_consent_outbox_state_after",
        ),
        sa.CheckConstraint(
            "policy_version ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_consent_outbox_policy_version",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'published', 'failed')",
            name="ck_consent_outbox_delivery_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_consent_outbox_attempt_count"),
        sa.CheckConstraint(
            "(delivery_status = 'published') = (published_at IS NOT NULL)",
            name="ck_consent_outbox_published_state",
        ),
        sa.ForeignKeyConstraint(
            ["consent_event_id"],
            ["privacy.consent_events.consent_event_id"],
            name="fk_consent_outbox_event_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("consent_event_id", name="uq_consent_outbox_event_id"),
        sa.UniqueConstraint("source_event_id", name="uq_consent_outbox_source_event_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_consent_outbox_pending",
        "consent_audit_outbox",
        ["delivery_status", "created_at"],
        schema=SCHEMA,
        postgresql_where=sa.text("delivery_status IN ('pending', 'failed')"),
    )


def _protect_history() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION privacy.reject_append_only_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            SECURITY INVOKER
            SET search_path = pg_catalog
            AS $privacy$
            BEGIN
                RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'consent history is append-only';
            END;
            $privacy$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER consent_events_reject_update_delete
            BEFORE UPDATE OR DELETE ON privacy.consent_events
            FOR EACH ROW EXECUTE FUNCTION privacy.reject_append_only_mutation()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER consent_events_reject_truncate
            BEFORE TRUNCATE ON privacy.consent_events
            FOR EACH STATEMENT EXECUTE FUNCTION privacy.reject_append_only_mutation()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION privacy.reject_consent_delete()
            RETURNS trigger
            LANGUAGE plpgsql
            SECURITY INVOKER
            SET search_path = pg_catalog
            AS $privacy$
            BEGIN
                RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'consent records cannot be deleted';
            END;
            $privacy$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER consents_reject_delete
            BEFORE DELETE ON privacy.consents
            FOR EACH ROW EXECUTE FUNCTION privacy.reject_consent_delete()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER consents_reject_truncate
            BEFORE TRUNCATE ON privacy.consents
            FOR EACH STATEMENT EXECUTE FUNCTION privacy.reject_consent_delete()
            """
        )
    )
    for statement in (
        "ALTER TABLE privacy.consent_events ENABLE ALWAYS TRIGGER consent_events_reject_update_delete",
        "ALTER TABLE privacy.consent_events ENABLE ALWAYS TRIGGER consent_events_reject_truncate",
        "ALTER TABLE privacy.consents ENABLE ALWAYS TRIGGER consents_reject_delete",
        "ALTER TABLE privacy.consents ENABLE ALWAYS TRIGGER consents_reject_truncate",
        "REVOKE CREATE ON SCHEMA privacy FROM PUBLIC",
        "REVOKE UPDATE, DELETE, TRUNCATE ON privacy.consent_events FROM PUBLIC",
        "REVOKE DELETE, TRUNCATE ON privacy.consents FROM PUBLIC",
    ):
        op.execute(sa.text(statement))


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    _create_purposes()
    _create_consents()
    _create_consent_events()
    _create_audit_outbox()
    _protect_history()


def downgrade() -> None:
    op.drop_table("consent_audit_outbox", schema=SCHEMA)
    op.drop_table("consent_events", schema=SCHEMA)
    op.drop_table("consents", schema=SCHEMA)
    op.drop_table("purposes", schema=SCHEMA)
    op.execute(sa.text("DROP FUNCTION privacy.reject_consent_delete()"))
    op.execute(sa.text("DROP FUNCTION privacy.reject_append_only_mutation()"))
    op.execute(sa.schema.DropSchema(SCHEMA))
