"""Create the Identity Service authentication runtime schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from camera_ai_crypto import encv1_check_constraint
from sqlalchemy.dialects import postgresql

revision = "20260728_0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "identity"


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("login_lookup_digest", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "octet_length(login_lookup_digest) = 32",
            name="ck_identity_users_login_digest",
        ),
        sa.CheckConstraint(
            "status IN ('pending','active','locked','disabled')",
            name="ck_identity_users_status",
        ),
        sa.UniqueConstraint("tenant_id", "login_lookup_digest", name="uq_identity_user_login"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_identity_users_school_status",
        "users",
        ["school_id", "status"],
        schema=SCHEMA,
    )
    op.create_table(
        "credentials",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.user_id"],
            name="fk_identity_credentials_user",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "password_hash LIKE '$argon2id$%' AND length(password_hash) BETWEEN 64 AND 512",
            name="ck_identity_credentials_argon2id",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "roles",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "code ~ '^[a-z][a-z0-9_.:-]{0,63}$'",
            name="ck_identity_roles_code",
        ),
        sa.CheckConstraint("status IN ('active','retired')", name="ck_identity_roles_status"),
        sa.UniqueConstraint("code", name="uq_identity_roles_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "user_role_assignments",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.user_id"],
            name="fk_identity_assignments_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["identity.roles.role_id"],
            name="fk_identity_assignments_role",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at",
            name="ck_identity_assignments_timestamps",
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_identity_user_role"),
        schema=SCHEMA,
    )
    op.create_table(
        "sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.user_id"],
            name="fk_identity_sessions_user",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "expires_at > issued_at AND (revoked_at IS NULL OR revoked_at >= issued_at)",
            name="ck_identity_sessions_timestamps",
        ),
        sa.UniqueConstraint("family_id", name="uq_identity_sessions_family"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_identity_sessions_user_active",
        "sessions",
        ["user_id", "revoked_at", "expires_at"],
        schema=SCHEMA,
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("refresh_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["identity.sessions.session_id"],
            name="fk_identity_refresh_session",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="ck_identity_refresh_hash"),
        sa.CheckConstraint(
            "state IN ('active','rotated','revoked')",
            name="ck_identity_refresh_state",
        ),
        sa.CheckConstraint(
            "expires_at > issued_at"
            " AND ((state = 'active' AND rotated_at IS NULL)"
            " OR (state = 'rotated' AND rotated_at IS NOT NULL)"
            " OR state = 'revoked')",
            name="ck_identity_refresh_timestamps",
        ),
        sa.UniqueConstraint("token_hash", name="uq_identity_refresh_hash"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_identity_refresh_family_state",
        "refresh_tokens",
        ["family_id", "state", "expires_at"],
        schema=SCHEMA,
    )
    constraint_name, constraint_sql = encv1_check_constraint("mfa_factors", "secret_ciphertext")
    op.create_table(
        "mfa_factors",
        sa.Column("factor_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.user_id"],
            name="fk_identity_mfa_user",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(constraint_sql, name=constraint_name),
        sa.CheckConstraint(
            "state IN ('pending','active','revoked')",
            name="ck_identity_mfa_state",
        ),
        sa.CheckConstraint(
            "((state = 'active' AND verified_at IS NOT NULL)"
            " OR (state = 'pending' AND verified_at IS NULL)"
            " OR state = 'revoked')"
            " AND (verified_at IS NULL OR verified_at >= created_at)",
            name="ck_identity_mfa_timestamps",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_identity_mfa_user_state",
        "mfa_factors",
        ["user_id", "state", "verified_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "uq_identity_mfa_active_user",
        "mfa_factors",
        ["user_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("state = 'active'"),
    )
    op.create_table(
        "audit_outbox",
        sa.Column("audit_outbox_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_service", sa.Text(), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("publish_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_service = 'identity-service'",
            name="ck_identity_audit_source_service",
        ),
        sa.CheckConstraint(
            "publish_status IN ('pending','delivered','failed')",
            name="ck_identity_audit_status",
        ),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 5", name="ck_identity_audit_attempts"),
        sa.CheckConstraint(
            "payload ? 'event_schema_version' AND payload ? 'action'"
            " AND payload ? 'source_event_id' AND payload ? 'request_id'"
            " AND payload ? 'result' AND payload ? 'occurred_at'"
            " AND NOT (payload ?| ARRAY['password','password_hash','access_token',"
            "'refresh_token','token_hash','mfa_secret','secret_ciphertext','credential',"
            "'image_base64','face_embedding']::text[])",
            name="ck_identity_audit_payload",
        ),
        sa.UniqueConstraint("source_service", "source_event_id", name="uq_identity_audit_source"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_identity_audit_status_due",
        "audit_outbox",
        ["publish_status", "next_attempt_at", "recorded_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("audit_outbox", schema=SCHEMA)
    op.drop_table("mfa_factors", schema=SCHEMA)
    op.drop_table("refresh_tokens", schema=SCHEMA)
    op.drop_table("sessions", schema=SCHEMA)
    op.drop_table("user_role_assignments", schema=SCHEMA)
    op.drop_table("roles", schema=SCHEMA)
    op.drop_table("credentials", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
    op.execute(sa.schema.DropSchema(SCHEMA))
