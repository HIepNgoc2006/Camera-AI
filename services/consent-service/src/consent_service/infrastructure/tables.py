"""Consent Service-owned SQLAlchemy table metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="privacy")

purposes = sa.Table(
    "purposes",
    metadata,
    sa.Column("purpose_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("code", sa.Text(), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column("data_categories", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("requires_biometric_consent", sa.Boolean(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
    sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

consents = sa.Table(
    "consents",
    metadata,
    sa.Column("consent_id", postgresql.UUID(as_uuid=True), primary_key=True),
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
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("row_version", sa.BigInteger(), nullable=False),
)

consent_events = sa.Table(
    "consent_events",
    metadata,
    sa.Column("consent_event_id", postgresql.UUID(as_uuid=True), primary_key=True),
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
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)

consent_audit_outbox = sa.Table(
    "consent_audit_outbox",
    metadata,
    sa.Column("audit_intent_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("consent_event_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("event_schema_version", sa.SmallInteger(), nullable=False),
    sa.Column("source_service", sa.Text(), nullable=False),
    sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("action", sa.Text(), nullable=False),
    sa.Column("purpose_code", sa.Text(), nullable=False),
    sa.Column("resource_type", sa.Text(), nullable=False),
    sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("request_id", sa.Text(), nullable=False),
    sa.Column("result", sa.Text(), nullable=False),
    sa.Column("reason_code", sa.Text(), nullable=True),
    sa.Column("state_before", sa.Text(), nullable=True),
    sa.Column("state_after", sa.Text(), nullable=False),
    sa.Column("policy_version", sa.Text(), nullable=False),
    sa.Column("delivery_status", sa.Text(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
