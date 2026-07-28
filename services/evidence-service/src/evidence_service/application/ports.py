"""Ports owned by the Evidence Storage application layer."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from camera_ai_audit import AuditIntent

from evidence_service.domain.models import (
    AccessAction,
    ConsentState,
    EvidenceLink,
    EvidenceObject,
    EvidenceState,
    RequestContext,
    StoredObjectFacts,
)


class EvidenceRepository(Protocol):
    def create_with_audit(self, evidence: EvidenceObject, audit: AuditIntent) -> None: ...

    def get(
        self,
        evidence_id: UUID,
        *,
        tenant_id: UUID,
        school_id: UUID,
    ) -> EvidenceObject | None: ...

    def transition_with_audit(
        self,
        evidence: EvidenceObject,
        *,
        target: EvidenceState,
        changed_at: datetime,
        audit: AuditIntent,
        provider_version_ciphertext: bytes | None = None,
        facts: StoredObjectFacts | None = None,
        deletion_reason_code: str | None = None,
        deletion_job_ref: UUID | None = None,
        deletion_request_id: str | None = None,
        deletion_correlation_id: str | None = None,
    ) -> EvidenceObject: ...

    def add_link_with_audit(
        self,
        evidence: EvidenceObject,
        link: EvidenceLink,
        audit: AuditIntent,
    ) -> None: ...

    def reconcile_with_audit(
        self,
        evidence: EvidenceObject,
        *,
        matched: bool,
        changed_at: datetime,
        audit: AuditIntent,
    ) -> EvidenceObject: ...

    def schedule_retry(
        self,
        evidence: EvidenceObject,
        *,
        operation: str,
        error_code: str,
        changed_at: datetime,
    ) -> None: ...

    def append_audit(self, audit: AuditIntent) -> None: ...


class PrivateObjectStorage(Protocol):
    def presign_upload(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        content_type: str,
        maximum_size: int,
        retention_days: int,
        ttl_seconds: int,
    ) -> tuple[str, tuple[tuple[str, str], ...]]: ...

    def inspect(
        self,
        *,
        bucket_ref: str,
        object_key: str,
    ) -> StoredObjectFacts: ...

    def presign_get(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        provider_version: str | None,
        response_disposition: str,
        ttl_seconds: int,
    ) -> str: ...

    def delete(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        provider_version: str | None,
    ) -> None: ...


class ObjectLocatorProtector(Protocol):
    def protect(
        self,
        *,
        evidence_id: UUID,
        tenant_id: UUID,
        object_key: str,
        provider_version: str | None,
    ) -> tuple[bytes, bytes | None]: ...

    def reveal(
        self,
        *,
        evidence_id: UUID,
        tenant_id: UUID,
        object_key_ciphertext: bytes,
        provider_version_ciphertext: bytes | None,
    ) -> tuple[str, str | None]: ...

    def key_version(self, ciphertext: bytes) -> str: ...


class EvidenceAuthorization(Protocol):
    def authorize(
        self,
        *,
        context: RequestContext,
        evidence: EvidenceObject,
        action: AccessAction,
        consent_state: ConsentState,
        approval_status: str,
    ) -> bool: ...


class MetricsSink(Protocol):
    def increment(self, metric: str, *, outcome: str) -> None: ...

    def observe(self, metric: str, *, seconds: float) -> None: ...

    def set_gauge(self, metric: str, *, value: float) -> None: ...


class NullMetricsSink:
    def increment(self, metric: str, *, outcome: str) -> None:
        del metric, outcome

    def observe(self, metric: str, *, seconds: float) -> None:
        del metric, seconds

    def set_gauge(self, metric: str, *, value: float) -> None:
        del metric, value
