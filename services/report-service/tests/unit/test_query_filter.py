# mypy: disable-error-code="no-untyped-def,arg-type,no-untyped-call"

from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from report_service.domain.models import ReportQuery, RequestContext
from report_service.infrastructure.authorization import build_authorized_row_filter
from sqlalchemy.dialects import postgresql


def test_sql_filter_contains_tenant_scope_consent_and_retention():
    table = sa.table(
        "source_rows",
        sa.column("tenant_id"),
        sa.column("school_id"),
        sa.column("class_id"),
        sa.column("occurred_at"),
        sa.column("consent_state"),
        sa.column("retention_until"),
    )
    now = datetime(2026, 7, 30, tzinfo=UTC)
    query = ReportQuery(
        report_type="attendance_summary",
        school_ids=frozenset({UUID(int=3)}),
        class_ids=frozenset({UUID(int=4)}),
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    context = RequestContext(
        actor_id=UUID(int=1),
        tenant_id=UUID(int=2),
        authorized_school_ids=frozenset({UUID(int=3)}),
        authorized_class_ids=frozenset({UUID(int=4)}),
        permission_codes=frozenset({"report.view_metadata"}),
        request_id="req_synthetic123",
        correlation_id="cor_synthetic123",
        purpose_code="management_report",
        authenticated=True,
    )
    sql = str(
        build_authorized_row_filter(table=table, query=query, context=context, now=now).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "tenant_id" in sql
    assert "school_id" in sql
    assert "class_id" in sql
    assert "consent_state" in sql
    assert "retention_until" in sql
