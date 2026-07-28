from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from camera_ai_authorization import (
    RowScopeColumns,
    ScopeDimension,
    ScopeGrant,
    build_row_scope_filter,
    load_catalog,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CATALOG = load_catalog(
    REPO_ROOT / "packages" / "authorization-policy" / "permission-catalog-v1.json"
)
NOW = datetime(2026, 7, 28, 1, 30, tzinfo=UTC)


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def test_sql_scope_filter_prevents_cross_tenant_school_class_and_direct_id_leaks() -> None:
    metadata = sa.MetaData()
    records = sa.Table(
        "synthetic_attendance_records",
        metadata,
        sa.Column("record_id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("class_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("guardian_subject_ref", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("purpose_code", sa.String, nullable=False),
        sa.Column("consent_state", sa.String, nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("legal_hold_state", sa.String, nullable=False),
        sa.Column("resource_state", sa.String, nullable=False),
        sa.Column("sensitivity", sa.String, nullable=False),
    )
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    rows = [
        {
            "record_id": _uuid(1),
            "tenant_id": _uuid(10),
            "school_id": _uuid(11),
            "class_id": _uuid(12),
            "guardian_subject_ref": _uuid(13),
            "purpose_code": "attendance_management",
            "consent_state": "allowed",
            "retention_until": NOW + timedelta(days=1),
            "legal_hold_state": "none",
            "resource_state": "available",
            "sensitivity": "high",
        },
        {
            "record_id": _uuid(2),
            "tenant_id": _uuid(99),
            "school_id": _uuid(11),
            "class_id": _uuid(12),
            "guardian_subject_ref": _uuid(13),
            "purpose_code": "attendance_management",
            "consent_state": "allowed",
            "retention_until": NOW + timedelta(days=1),
            "legal_hold_state": "none",
            "resource_state": "available",
            "sensitivity": "high",
        },
        {
            "record_id": _uuid(3),
            "tenant_id": _uuid(10),
            "school_id": _uuid(98),
            "class_id": _uuid(97),
            "guardian_subject_ref": _uuid(96),
            "purpose_code": "attendance_management",
            "consent_state": "allowed",
            "retention_until": NOW + timedelta(days=1),
            "legal_hold_state": "none",
            "resource_state": "available",
            "sensitivity": "high",
        },
        {
            "record_id": _uuid(4),
            "tenant_id": _uuid(10),
            "school_id": _uuid(11),
            "class_id": _uuid(12),
            "guardian_subject_ref": _uuid(13),
            "purpose_code": "attendance_management",
            "consent_state": "blocked",
            "retention_until": NOW - timedelta(seconds=1),
            "legal_hold_state": "none",
            "resource_state": "available",
            "sensitivity": "high",
        },
    ]
    with engine.begin() as connection:
        connection.execute(records.insert(), rows)

    scope = ScopeGrant(
        tenant_id=_uuid(10),
        school_ids=frozenset({_uuid(11)}),
        dimension=ScopeDimension.CLASS,
        scope_ids=frozenset({_uuid(12)}),
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
    )
    predicate = build_row_scope_filter(
        rule=CATALOG.permission("attendance.view_metadata"),
        scope=scope,
        columns=RowScopeColumns(
            tenant_id=records.c.tenant_id,
            school_id=records.c.school_id,
            class_id=records.c.class_id,
            guardian_subject_ref=records.c.guardian_subject_ref,
            purpose_code=records.c.purpose_code,
            consent_state=records.c.consent_state,
            retention_until=records.c.retention_until,
            legal_hold_state=records.c.legal_hold_state,
            resource_state=records.c.resource_state,
            sensitivity=records.c.sensitivity,
        ),
        now=NOW,
    )
    with engine.connect() as connection:
        visible = (
            connection.execute(sa.select(records.c.record_id).where(predicate)).scalars().all()
        )
        foreign_direct = connection.execute(
            sa.select(records.c.record_id).where(
                records.c.record_id == _uuid(3),
                predicate,
            )
        ).scalar_one_or_none()

    assert visible == [_uuid(1)]
    assert foreign_direct is None


def test_missing_scope_binding_compiles_to_false_instead_of_fetch_then_filter() -> None:
    table = sa.table(
        "synthetic",
        sa.column("tenant_id"),
        sa.column("school_id"),
    )
    scope = ScopeGrant(
        tenant_id=_uuid(10),
        school_ids=frozenset({_uuid(11)}),
        dimension=ScopeDimension.CLASS,
        scope_ids=frozenset({_uuid(12)}),
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
    )

    predicate = build_row_scope_filter(
        rule=CATALOG.permission("attendance.view_metadata"),
        scope=scope,
        columns=RowScopeColumns(
            tenant_id=table.c.tenant_id,
            school_id=table.c.school_id,
        ),
        now=NOW,
    )

    assert str(predicate) == "false"
