"""Authorized report and export orchestration."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from camera_ai_audit import AuditIntent, IntentResult

from report_service.application.ports import (
    ExportArtifactStore,
    ExportQueue,
    ExportQuota,
    ExportRepository,
    MetricsSink,
    NullMetricsSink,
    ReportDataSource,
)
from report_service.domain.errors import ReportError
from report_service.domain.models import (
    AggregateCell,
    DownloadGrant,
    ExportCommand,
    ExportJob,
    ExportState,
    ReportQuery,
    RequestContext,
)
from report_service.domain.policies import (
    ARTIFACT_TTL_SECONDS,
    POLICY_VERSION,
    PolicyActivation,
    aggregate_cells,
    require_export,
    require_view,
    signed_get_ttl,
)

Clock = Callable[[], datetime]


def _audit(
    context: RequestContext,
    *,
    action: str,
    result: IntentResult,
    resource_id: UUID,
    occurred_at: datetime,
    reason_code: str | None = None,
    row_count: int | None = None,
) -> AuditIntent:
    return AuditIntent(
        source_service="report-service",
        source_event_id=uuid4(),
        action=action,
        resource_type="report_export" if action.startswith("REPORT_EXPORT") else "report",
        resource_id=resource_id,
        request_id=context.request_id,
        correlation_id=context.correlation_id,
        result=result,
        reason_code=reason_code,
        purpose_code=context.purpose_code,
        occurred_at=occurred_at,
        count_summary=() if row_count is None else (("record_count", row_count),),
        policy_versions=(("report_policy", POLICY_VERSION),),
    )


class ReportApplicationService:
    def __init__(
        self,
        data_source: ReportDataSource,
        repository: ExportRepository,
        queue: ExportQueue,
        quota: ExportQuota,
        artifacts: ExportArtifactStore,
        *,
        activation: PolicyActivation | None = None,
        metrics: MetricsSink | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._data_source = data_source
        self._repository = repository
        self._queue = queue
        self._quota = quota
        self._artifacts = artifacts
        self._activation = activation or PolicyActivation()
        self._metrics = metrics or NullMetricsSink()
        self._clock = clock or (lambda: datetime.now(UTC))

    def run_report(
        self, report_id: UUID, query: ReportQuery, context: RequestContext
    ) -> tuple[AggregateCell, ...]:
        now = self._clock()
        try:
            require_view(query, context)
            rows = self._data_source.fetch_authorized_rows(query, context, now=now)
            counts = Counter(row.category_code for row in rows)
            cells = aggregate_cells(
                dict(counts), sample_count=len(rows), activation=self._activation
            )
            self._repository.append_audit(
                _audit(
                    context,
                    action="REPORT_VIEW_GRANTED",
                    result=IntentResult.SUCCESS,
                    resource_id=report_id,
                    occurred_at=now,
                    row_count=len(rows),
                )
            )
            self._metrics.increment("report_query_total", outcome="granted")
            return cells
        except ReportError as exc:
            self._repository.append_audit(
                _audit(
                    context,
                    action="REPORT_VIEW_DENIED",
                    result=IntentResult.DENIED,
                    resource_id=report_id,
                    occurred_at=now,
                    reason_code=exc.code,
                )
            )
            self._metrics.increment("report_query_total", outcome="denied")
            raise

    def request_export(self, command: ExportCommand, context: RequestContext) -> ExportJob:
        now = self._clock()
        existing = self._repository.find_by_idempotency(context.tenant_id, command.idempotency_key)
        if existing is not None:
            return existing
        try:
            require_export(command, context)
            retry_after = self._quota.retry_after_seconds(context.actor_id)
            if retry_after is not None:
                raise ReportError(
                    "REPORT_EXPORT_QUOTA_EXCEEDED",
                    retry_after_seconds=retry_after,
                )
            export_id = uuid4()
            job = ExportJob(
                export_id=export_id,
                actor_id=context.actor_id,
                tenant_id=context.tenant_id,
                query=command.query,
                reason_code=command.reason_code,
                format_code=command.format_code,
                state=ExportState.QUEUED,
                created_at=now,
                expires_at=now + timedelta(seconds=ARTIFACT_TTL_SECONDS),
            )
            self._repository.create_with_audit(
                job,
                command.idempotency_key,
                _audit(
                    context,
                    action="REPORT_EXPORT_REQUESTED",
                    result=IntentResult.SUCCESS,
                    resource_id=export_id,
                    occurred_at=now,
                ),
            )
            self._queue.enqueue(export_id)
            self._metrics.increment("report_export_total", outcome="queued")
            return job
        except ReportError as exc:
            self._repository.append_audit(
                _audit(
                    context,
                    action="REPORT_EXPORT_DENIED",
                    result=IntentResult.DENIED,
                    resource_id=uuid4(),
                    occurred_at=now,
                    reason_code=exc.code,
                )
            )
            self._metrics.increment("report_export_total", outcome="denied")
            raise

    def generate_export(self, export_id: UUID, context: RequestContext) -> ExportJob:
        now = self._clock()
        job = self._owned(export_id, context)
        command = ExportCommand(
            query=job.query,
            reason_code=job.reason_code,
            approval_status="approved" if job.query.cross_scope else "not_required",
            format_code=job.format_code,
            idempotency_key="generation-recheck-v1",
        )
        require_export(command, context)
        if job.state is not ExportState.QUEUED or job.expires_at <= now:
            raise ReportError("REPORT_EXPORT_NOT_AVAILABLE")
        rows = self._data_source.fetch_authorized_rows(job.query, context, now=now)
        artifact_ref = self._artifacts.write_private(job.export_id, job.format_code, rows)
        generated = replace(
            job,
            state=ExportState.AVAILABLE,
            artifact_ref=artifact_ref,
            row_count=len(rows),
        )
        self._repository.save_with_audit(
            generated,
            _audit(
                context,
                action="REPORT_EXPORT_GENERATED",
                result=IntentResult.SUCCESS,
                resource_id=job.export_id,
                occurred_at=now,
                row_count=len(rows),
            ),
        )
        self._metrics.increment("report_export_total", outcome="generated")
        return generated

    def download_export(
        self,
        export_id: UUID,
        context: RequestContext,
        *,
        ttl_seconds: int | None = None,
    ) -> DownloadGrant:
        now = self._clock()
        job = self._owned(export_id, context)
        command = ExportCommand(
            query=job.query,
            reason_code=job.reason_code,
            approval_status="approved" if job.query.cross_scope else "not_required",
            format_code=job.format_code,
            idempotency_key="download-recheck-v1",
        )
        require_export(command, context)
        if (
            job.state is not ExportState.AVAILABLE
            or job.expires_at <= now
            or job.artifact_ref is None
        ):
            raise ReportError("REPORT_EXPORT_NOT_AVAILABLE")
        ttl = signed_get_ttl(ttl_seconds)
        url = self._artifacts.presign_get(job.artifact_ref, ttl_seconds=ttl)
        self._repository.append_audit(
            _audit(
                context,
                action="REPORT_EXPORT_DOWNLOADED",
                result=IntentResult.SUCCESS,
                resource_id=job.export_id,
                occurred_at=now,
                row_count=job.row_count,
            )
        )
        self._metrics.increment("report_export_total", outcome="downloaded")
        return DownloadGrant(job.export_id, now + timedelta(seconds=ttl), url)

    def expire_export(self, export_id: UUID, context: RequestContext) -> ExportJob:
        now = self._clock()
        job = self._owned(export_id, context)
        if job.expires_at > now or job.state is ExportState.EXPIRED:
            raise ReportError("REPORT_EXPORT_NOT_EXPIRED")
        expired = replace(job, state=ExportState.EXPIRED, artifact_ref=None)
        self._repository.save_with_audit(
            expired,
            _audit(
                context,
                action="REPORT_EXPORT_EXPIRED",
                result=IntentResult.SUCCESS,
                resource_id=job.export_id,
                occurred_at=now,
                row_count=job.row_count,
            ),
        )
        if job.artifact_ref is not None:
            self._artifacts.delete(job.artifact_ref)
        self._metrics.increment("report_export_total", outcome="expired")
        return expired

    def _owned(self, export_id: UUID, context: RequestContext) -> ExportJob:
        job = self._repository.get(export_id, context.tenant_id)
        if job is None or job.actor_id != context.actor_id:
            raise ReportError("REPORT_NOT_FOUND")
        return job


def scope_fingerprint(query: ReportQuery) -> bytes:
    material = "|".join(
        (
            query.report_type,
            ",".join(sorted(str(value) for value in query.school_ids)),
            ",".join(sorted(str(value) for value in query.class_ids)),
            query.period_start.isoformat(),
            query.period_end.isoformat(),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).digest()
