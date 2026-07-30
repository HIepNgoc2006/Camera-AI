"""Fail-closed report/export policy."""

from __future__ import annotations

from dataclasses import dataclass

from report_service.domain.errors import ReportError
from report_service.domain.models import AggregateCell, ExportCommand, ReportQuery, RequestContext

POLICY_VERSION = "report_export_policy_v1"
ARTIFACT_TTL_SECONDS = 7 * 24 * 60 * 60
SIGNED_GET_DEFAULT_SECONDS = 60
SIGNED_GET_HARD_MAX_SECONDS = 300
_REASONS = frozenset(
    {
        "ATTENDANCE_AUDIT",
        "TIMEKEEPING_AUDIT",
        "VIOLATION_REVIEW",
        "SECURITY_INVESTIGATION",
        "LEGAL_REQUEST",
        "DATA_SUBJECT_REQUEST",
        "MANAGEMENT_REPORT",
    }
)


@dataclass(frozen=True, slots=True)
class PolicyActivation:
    minimum_cohort_size: int | None = None
    privacy_legal_approved: bool = False
    security_ops_approved: bool = False
    business_owner_approved: bool = False
    policy_version: str = POLICY_VERSION

    @property
    def active(self) -> bool:
        return (
            self.policy_version == POLICY_VERSION
            and self.minimum_cohort_size is not None
            and 2 <= self.minimum_cohort_size <= 100
            and self.privacy_legal_approved
            and self.security_ops_approved
            and self.business_owner_approved
        )


def require_scope(query: ReportQuery, context: RequestContext) -> None:
    if (
        not context.authenticated
        or not query.school_ids.issubset(context.authorized_school_ids)
        or not query.class_ids.issubset(context.authorized_class_ids)
    ):
        raise ReportError("REPORT_NOT_FOUND")


def require_view(query: ReportQuery, context: RequestContext) -> None:
    require_scope(query, context)
    if "report.view_metadata" not in context.permission_codes:
        raise ReportError("REPORT_NOT_FOUND")


def require_export(command: ExportCommand, context: RequestContext) -> None:
    require_scope(command.query, context)
    if "report.export" not in context.permission_codes:
        raise ReportError("REPORT_NOT_FOUND")
    if command.reason_code not in _REASONS:
        raise ReportError("REPORT_REASON_INVALID")
    if command.query.cross_scope and command.approval_status != "approved":
        raise ReportError("REPORT_EXPORT_APPROVAL_REQUIRED")
    if not command.query.cross_scope and command.approval_status not in {
        "not_required",
        "approved",
    }:
        raise ReportError("REPORT_EXPORT_APPROVAL_REQUIRED")


def aggregate_cells(
    category_counts: dict[str, int],
    *,
    sample_count: int,
    activation: PolicyActivation,
) -> tuple[AggregateCell, ...]:
    suppressed = (
        not activation.active
        or activation.minimum_cohort_size is None
        or sample_count < activation.minimum_cohort_size
    )
    return tuple(
        AggregateCell(
            category_code=category,
            count=None if suppressed else count,
            sample_count=sample_count,
            suppressed=suppressed,
            policy_version=POLICY_VERSION,
        )
        for category, count in sorted(category_counts.items())
    )


def signed_get_ttl(requested: int | None) -> int:
    ttl = SIGNED_GET_DEFAULT_SECONDS if requested is None else requested
    if not 1 <= ttl <= SIGNED_GET_HARD_MAX_SECONDS:
        raise ReportError("REPORT_DOWNLOAD_INVALID")
    return ttl
