"""Composable SQL predicates that enforce scope before protected rows are fetched."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement

from camera_ai_authorization.catalog import PermissionRule
from camera_ai_authorization.models import ScopeDimension, ScopeGrant


@dataclass(frozen=True, slots=True)
class RowScopeColumns:
    tenant_id: ColumnElement[Any]
    school_id: ColumnElement[Any]
    class_id: ColumnElement[Any] | None = None
    guardian_subject_ref: ColumnElement[Any] | None = None
    kitchen_zone_id: ColumnElement[Any] | None = None
    purpose_code: ColumnElement[Any] | None = None
    consent_state: ColumnElement[Any] | None = None
    retention_until: ColumnElement[Any] | None = None
    legal_hold_state: ColumnElement[Any] | None = None
    resource_state: ColumnElement[Any] | None = None
    sensitivity: ColumnElement[Any] | None = None


def _scope_column(
    columns: RowScopeColumns,
    dimension: ScopeDimension,
) -> ColumnElement[Any] | None:
    return {
        ScopeDimension.SCHOOL: columns.school_id,
        ScopeDimension.CLASS: columns.class_id,
        ScopeDimension.GUARDIAN_SUBJECT: columns.guardian_subject_ref,
        ScopeDimension.KITCHEN_ZONE: columns.kitchen_zone_id,
    }[dimension]


def build_row_scope_filter(
    *,
    rule: PermissionRule,
    scope: ScopeGrant,
    columns: RowScopeColumns,
    now: datetime,
) -> ColumnElement[bool]:
    """Return SQL false for incomplete bindings; never fall back to post-fetch filtering."""

    if (
        now.tzinfo is None
        or now.utcoffset() is None
        or not scope.is_current(now)
        or scope.dimension not in rule.scope_dimensions
    ):
        return sa.false()
    scope_column = _scope_column(columns, scope.dimension)
    if scope_column is None:
        return sa.false()
    conditions: list[ColumnElement[bool]] = [
        columns.tenant_id == scope.tenant_id,
        columns.school_id.in_(scope.school_ids),
        scope_column.in_(scope.scope_ids),
    ]
    required = rule.required_attributes
    required_columns = {
        "purpose_code": columns.purpose_code,
        "consent_state": columns.consent_state,
        "retention_state": columns.retention_until,
        "legal_hold_state": columns.legal_hold_state,
        "resource_state": columns.resource_state,
        "sensitivity": columns.sensitivity,
    }
    if any(required_columns[name] is None for name in required & required_columns.keys()):
        return sa.false()
    if "purpose_code" in required:
        assert columns.purpose_code is not None
        conditions.append(columns.purpose_code.in_(rule.allowed_purpose_codes))
    if "consent_state" in required:
        assert columns.consent_state is not None
        allowed_consent = (
            ("allowed",) if rule.consent_requirement == "required" else ("allowed", "not_required")
        )
        conditions.append(columns.consent_state.in_(allowed_consent))
    if "retention_state" in required:
        assert columns.retention_until is not None
        conditions.append(columns.retention_until > now)
    if "legal_hold_state" in required:
        assert columns.legal_hold_state is not None
        conditions.append(columns.legal_hold_state.in_(("none", "active", "released")))
        if rule.deny_when_legal_hold_active:
            conditions.append(columns.legal_hold_state != "active")
    if "resource_state" in required:
        assert columns.resource_state is not None
        conditions.append(columns.resource_state == "available")
    if "sensitivity" in required:
        assert columns.sensitivity is not None
        conditions.append(columns.sensitivity.in_(("high", "critical")))
    return sa.and_(*conditions)
