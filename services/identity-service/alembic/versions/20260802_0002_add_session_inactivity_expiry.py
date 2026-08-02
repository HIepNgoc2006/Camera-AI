"""Add authoritative inactivity expiry to Identity sessions.

Revision ID: 20260802_0002
Revises: 20260728_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0002"
down_revision: str | None = "20260728_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )
    op.add_column(
        "sessions",
        sa.Column("inactivity_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )

    # Existing sessions predate this policy and have no trustworthy activity signal.
    # Backfill them at the closed boundary so they must authenticate again.
    op.execute(
        """
        UPDATE identity.sessions
        SET last_activity_at = issued_at,
            inactivity_expires_at = issued_at
        """
    )
    op.alter_column("sessions", "last_activity_at", nullable=False, schema="identity")
    op.alter_column("sessions", "inactivity_expires_at", nullable=False, schema="identity")
    op.create_check_constraint(
        "ck_identity_sessions_activity_window",
        "sessions",
        "issued_at <= last_activity_at "
        "AND last_activity_at <= inactivity_expires_at "
        "AND inactivity_expires_at <= expires_at",
        schema="identity",
    )
    op.create_index(
        "ix_identity_sessions_activity_active",
        "sessions",
        ["user_id", "revoked_at", "inactivity_expires_at", "expires_at"],
        schema="identity",
    )


def downgrade() -> None:
    # The previous runtime cannot enforce inactivity. Revoke every remaining
    # session before removing the columns so rollback cannot reactivate it.
    op.execute(
        """
        UPDATE identity.sessions
        SET revoked_at = COALESCE(revoked_at, GREATEST(CURRENT_TIMESTAMP, issued_at))
        """
    )
    op.drop_index(
        "ix_identity_sessions_activity_active",
        table_name="sessions",
        schema="identity",
    )
    op.drop_constraint(
        "ck_identity_sessions_activity_window",
        "sessions",
        schema="identity",
        type_="check",
    )
    op.drop_column("sessions", "inactivity_expires_at", schema="identity")
    op.drop_column("sessions", "last_activity_at", schema="identity")
