"""Report Service ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from camera_ai_audit import AuditIntent

from report_service.domain.models import ExportJob, ReportQuery, ReportRow, RequestContext


class ReportDataSource(Protocol):
    def fetch_authorized_rows(
        self,
        query: ReportQuery,
        context: RequestContext,
        *,
        now: datetime,
    ) -> tuple[ReportRow, ...]: ...


class ExportRepository(Protocol):
    def find_by_idempotency(self, tenant_id: UUID, key: str) -> ExportJob | None: ...

    def create_with_audit(self, job: ExportJob, key: str, audit: AuditIntent) -> None: ...

    def get(self, export_id: UUID, tenant_id: UUID) -> ExportJob | None: ...

    def save_with_audit(self, job: ExportJob, audit: AuditIntent) -> None: ...

    def append_audit(self, audit: AuditIntent) -> None: ...


class ExportQueue(Protocol):
    def enqueue(self, export_id: UUID) -> None: ...


class ExportQuota(Protocol):
    def retry_after_seconds(self, actor_id: UUID) -> int | None: ...


class ExportArtifactStore(Protocol):
    def write_private(
        self, export_id: UUID, format_code: str, rows: tuple[ReportRow, ...]
    ) -> UUID: ...

    def presign_get(self, artifact_ref: UUID, *, ttl_seconds: int) -> str: ...

    def delete(self, artifact_ref: UUID) -> None: ...


class MetricsSink(Protocol):
    def increment(self, metric: str, *, outcome: str) -> None: ...

    def set_gauge(self, metric: str, *, value: float) -> None: ...


class NullMetricsSink:
    def increment(self, metric: str, *, outcome: str) -> None:
        del metric, outcome

    def set_gauge(self, metric: str, *, value: float) -> None:
        del metric, value
