"""Identity Service-owned SQLAlchemy metadata."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="identity")

users = sa.Table(
    "users",
    metadata,
    sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("login_lookup_digest", sa.LargeBinary(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tenant_id", "login_lookup_digest", name="uq_identity_user_login"),
)

credentials = sa.Table(
    "credentials",
    metadata,
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("identity.users.user_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    sa.Column("password_hash", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

roles = sa.Table(
    "roles",
    metadata,
    sa.Column("role_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("code", sa.Text(), nullable=False, unique=True),
    sa.Column("status", sa.Text(), nullable=False),
)

user_role_assignments = sa.Table(
    "user_role_assignments",
    metadata,
    sa.Column("assignment_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("identity.users.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "role_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("identity.roles.role_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("user_id", "role_id", name="uq_identity_user_role"),
)

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("identity.users.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("mfa_verified", sa.Boolean(), nullable=False),
    sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("inactivity_expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
)

refresh_tokens = sa.Table(
    "refresh_tokens",
    metadata,
    sa.Column("refresh_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "session_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("identity.sessions.session_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True),
    sa.Column("state", sa.Text(), nullable=False),
    sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
)

mfa_factors = sa.Table(
    "mfa_factors",
    metadata,
    sa.Column("factor_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("identity.users.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
)

audit_outbox = sa.Table(
    "audit_outbox",
    metadata,
    sa.Column("audit_outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("source_service", sa.Text(), nullable=False),
    sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("payload", postgresql.JSONB(), nullable=False),
    sa.Column("publish_status", sa.Text(), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("source_service", "source_event_id", name="uq_identity_audit_source"),
)
