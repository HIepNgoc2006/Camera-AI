"""Query-time report row filters."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement

from report_service.domain.models import ReportQuery, RequestContext


def build_authorized_row_filter(
    *,
    table: sa.Table,
    query: ReportQuery,
    context: RequestContext,
    now: datetime,
) -> ColumnElement[bool]:
    """Fail closed unless every scope/privacy column exists and is filtered in SQL."""

    required = {
        "tenant_id",
        "school_id",
        "class_id",
        "occurred_at",
        "consent_state",
        "retention_until",
    }
    if not required.issubset(table.c.keys()) or not context.authenticated:
        return sa.false()
    return sa.and_(
        table.c.tenant_id == context.tenant_id,
        table.c.school_id.in_(query.school_ids & context.authorized_school_ids),
        sa.or_(
            table.c.class_id.is_(None),
            table.c.class_id.in_(query.class_ids & context.authorized_class_ids),
        ),
        table.c.occurred_at >= query.period_start,
        table.c.occurred_at < query.period_end,
        table.c.consent_state.in_(("allowed", "not_required")),
        table.c.retention_until > now,
    )
