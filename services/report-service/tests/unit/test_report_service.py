# mypy: disable-error-code="no-untyped-def,no-untyped-call"

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from report_service.application.service import ReportApplicationService
from report_service.domain.errors import ReportError
from report_service.domain.models import (
    ConsentState,
    ExportCommand,
    ExportState,
    ReportQuery,
    ReportRow,
    RequestContext,
)
from report_service.domain.policies import PolicyActivation, aggregate_cells, signed_get_ttl

NOW = datetime(2026, 7, 30, tzinfo=UTC)
SYNTHETIC_IDEMPOTENCY = "fixture-key-" + ("0" * 16)


class Fakes:
    def __init__(self, rows=()):
        self.rows = rows
        self.jobs = {}
        self.keys = {}
        self.audits = []
        self.enqueued = []
        self.artifacts = {}

    def fetch_authorized_rows(self, query, context, *, now):
        return tuple(
            row
            for row in self.rows
            if row.school_id in query.school_ids & context.authorized_school_ids
            and (
                row.class_id is None
                or row.class_id in query.class_ids & context.authorized_class_ids
            )
            and row.consent_state in {ConsentState.ALLOWED, ConsentState.NOT_REQUIRED}
            and row.retention_until > now
        )

    def find_by_idempotency(self, tenant_id, key):
        export_id = self.keys.get((tenant_id, key))
        return None if export_id is None else self.jobs[export_id]

    def create_with_audit(self, job, key, audit):
        self.jobs[job.export_id] = job
        self.keys[(job.tenant_id, key)] = job.export_id
        self.audits.append(audit)

    def get(self, export_id, tenant_id):
        job = self.jobs.get(export_id)
        return job if job is not None and job.tenant_id == tenant_id else None

    def save_with_audit(self, job, audit):
        self.jobs[job.export_id] = job
        self.audits.append(audit)

    def append_audit(self, audit):
        self.audits.append(audit)

    def enqueue(self, export_id):
        self.enqueued.append(export_id)

    def retry_after_seconds(self, actor_id):
        return None

    def write_private(self, export_id, format_code, rows):
        artifact = uuid4()
        self.artifacts[artifact] = len(rows)
        return artifact

    def presign_get(self, artifact_ref, *, ttl_seconds):
        return "https://storage.invalid/private"

    def delete(self, artifact_ref):
        self.artifacts.pop(artifact_ref, None)


def context(*permissions: str) -> RequestContext:
    return RequestContext(
        actor_id=UUID(int=1),
        tenant_id=UUID(int=2),
        authorized_school_ids=frozenset({UUID(int=3)}),
        authorized_class_ids=frozenset({UUID(int=4)}),
        permission_codes=frozenset(permissions),
        request_id="req_synthetic123",
        correlation_id="cor_synthetic123",
        purpose_code="management_report",
        authenticated=True,
    )


def query(*, extra_class=False) -> ReportQuery:
    classes = {UUID(int=4), UUID(int=5)} if extra_class else {UUID(int=4)}
    return ReportQuery(
        report_type="attendance_summary",
        school_ids=frozenset({UUID(int=3)}),
        class_ids=frozenset(classes),
        period_start=NOW - timedelta(days=1),
        period_end=NOW + timedelta(days=1),
    )


def test_default_cohort_policy_suppresses_and_approved_policy_reveals_counts():
    assert (
        aggregate_cells({"present": 3}, sample_count=3, activation=PolicyActivation())[0].count
        is None
    )
    active = PolicyActivation(3, True, True, True)
    assert aggregate_cells({"present": 3}, sample_count=3, activation=active)[0].count == 3


def test_view_only_cannot_export_and_denial_is_audited():
    fake = Fakes()
    service = ReportApplicationService(fake, fake, fake, fake, fake, clock=lambda: NOW)
    command = ExportCommand(
        query=query(),
        reason_code="MANAGEMENT_REPORT",
        approval_status="not_required",
        format_code="csv",
        idempotency_key=SYNTHETIC_IDEMPOTENCY + "1",
    )
    with pytest.raises(ReportError, match="REPORT_NOT_FOUND"):
        service.request_export(command, context("report.view_metadata"))
    assert fake.audits[-1].action == "REPORT_EXPORT_DENIED"


def test_cross_class_export_requires_approval():
    command = ExportCommand(
        query=query(extra_class=True),
        reason_code="MANAGEMENT_REPORT",
        approval_status="not_required",
        format_code="csv",
        idempotency_key=SYNTHETIC_IDEMPOTENCY + "2",
    )
    fake = Fakes()
    service = ReportApplicationService(fake, fake, fake, fake, fake, clock=lambda: NOW)
    with pytest.raises(ReportError, match="REPORT_NOT_FOUND|REPORT_EXPORT_APPROVAL_REQUIRED"):
        service.request_export(command, context("report.export"))


def test_export_lifecycle_reauthorizes_and_never_persists_signed_url():
    row = ReportRow(
        school_id=UUID(int=3),
        class_id=UUID(int=4),
        category_code="present",
        occurred_at=NOW,
        consent_state=ConsentState.ALLOWED,
        retention_until=NOW + timedelta(days=1),
        legal_hold_active=True,
    )
    fake = Fakes((row,))
    service = ReportApplicationService(fake, fake, fake, fake, fake, clock=lambda: NOW)
    command = ExportCommand(
        query=query(),
        reason_code="MANAGEMENT_REPORT",
        approval_status="not_required",
        format_code="csv",
        idempotency_key=SYNTHETIC_IDEMPOTENCY + "3",
    )
    ctx = context("report.export")
    job = service.request_export(command, ctx)
    generated = service.generate_export(job.export_id, ctx)
    grant = service.download_export(job.export_id, ctx)
    assert generated.state is ExportState.AVAILABLE
    assert generated.row_count == 1
    assert "signed_url=<redacted>" in repr(grant)
    assert all("signed_url" not in str(audit.publisher_payload()) for audit in fake.audits)


@pytest.mark.parametrize("ttl", [0, -1, 301])
def test_signed_get_bounds(ttl):
    with pytest.raises(ReportError, match="REPORT_DOWNLOAD_INVALID"):
        signed_get_ttl(ttl)
