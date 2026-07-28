"""Evidence lifecycle orchestration with fail-closed authorization and audit."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from camera_ai_audit import AuditIntent, IntentResult

from evidence_service.application.ports import (
    EvidenceAuthorization,
    EvidenceRepository,
    MetricsSink,
    NullMetricsSink,
    ObjectLocatorProtector,
    PrivateObjectStorage,
)
from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.media import validate_media
from evidence_service.domain.models import (
    AccessAction,
    AccessGrant,
    AccessRequest,
    ConsentState,
    EvidenceLink,
    EvidenceObject,
    EvidenceState,
    LegalHoldState,
    RequestContext,
    ScanState,
    UploadCommand,
    UploadTicket,
)
from evidence_service.domain.policies import (
    POLICY_VERSION,
    PolicyActivation,
    access_ttl,
    assert_access_preconditions,
    audit_actions,
    new_object_key,
    require_transition,
    validate_selection,
)

Clock = Callable[[], datetime]
IdentifierFactory = Callable[[], UUID]


def _audit(
    *,
    context: RequestContext,
    evidence_id: UUID,
    action: str,
    result: IntentResult,
    occurred_at: datetime,
    reason_code: str | None = None,
    source_event_id: UUID | None = None,
) -> AuditIntent:
    return AuditIntent(
        source_service="evidence-storage-service",
        source_event_id=source_event_id or uuid4(),
        action=action,
        resource_type="evidence",
        resource_id=evidence_id,
        request_id=context.request_id,
        correlation_id=context.correlation_id,
        result=result,
        reason_code=reason_code,
        purpose_code=context.purpose_code,
        school_id=context.school_id,
        occurred_at=occurred_at,
        policy_versions=(("evidence_policy", POLICY_VERSION),),
    )


class EvidenceApplicationService:
    def __init__(
        self,
        repository: EvidenceRepository,
        storage: PrivateObjectStorage,
        protector: ObjectLocatorProtector,
        authorization: EvidenceAuthorization,
        *,
        activation: PolicyActivation | None = None,
        metrics: MetricsSink | None = None,
        clock: Clock | None = None,
        identifier_factory: IdentifierFactory = uuid4,
        bucket_ref: str = "evidence-private-v1",
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._protector = protector
        self._authorization = authorization
        self._activation = activation or PolicyActivation()
        self._metrics = metrics or NullMetricsSink()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._identifier_factory = identifier_factory
        self._bucket_ref = bucket_ref

    def request_upload(
        self,
        command: UploadCommand,
        context: RequestContext,
    ) -> UploadTicket:
        now = self._clock()
        if (
            not context.actor_authenticated
            or command.retention_expires_at <= now
            or command.retention_expires_at > now + timedelta(days=command.retention_days)
            or command.captured_at > now
            or (
                command.media_kind.value == "image"
                and command.declared_size_bytes > 10 * 1024 * 1024
            )
            or (
                command.media_kind.value == "video"
                and command.declared_size_bytes > 250 * 1024 * 1024
            )
        ):
            raise EvidenceError("EVIDENCE_REQUEST_INVALID")
        evidence_id = self._identifier_factory()
        object_key = new_object_key()
        key_ciphertext, _ = self._protector.protect(
            evidence_id=evidence_id,
            tenant_id=context.tenant_id,
            object_key=object_key,
            provider_version=None,
        )
        evidence = EvidenceObject(
            evidence_id=evidence_id,
            tenant_id=context.tenant_id,
            school_id=context.school_id,
            source_event_id=command.source_event_id,
            camera_id=command.camera_id,
            task_id=command.task_id,
            captured_at=command.captured_at,
            received_at=now,
            object_key_ciphertext=key_ciphertext,
            bucket_ref=self._bucket_ref,
            provider_version_ciphertext=None,
            encryption_key_version_ref=self._protector.key_version(key_ciphertext),
            media_kind=command.media_kind,
            content_type=command.content_type,
            original_extension=command.original_extension.casefold().lstrip("."),
            size_bytes=command.declared_size_bytes,
            sha256=None,
            width=None,
            height=None,
            duration_ms=None,
            sensitivity=command.sensitivity,
            purpose_code=context.purpose_code,
            state=EvidenceState.PENDING_UPLOAD,
            scan_state=ScanState.PENDING,
            retention_policy_version=command.retention_policy_version,
            retention_days=command.retention_days,
            retention_expires_at=command.retention_expires_at,
            legal_hold_state=LegalHoldState.NONE,
            created_actor_id=context.actor_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            deletion_reason_code=None,
            deletion_job_ref=None,
            deletion_request_id=None,
            deletion_correlation_id=None,
            row_version=1,
        )
        audit = _audit(
            context=context,
            evidence_id=evidence_id,
            action="EVIDENCE_UPLOAD_REQUESTED",
            result=IntentResult.SUCCESS,
            occurred_at=now,
            source_event_id=self._identifier_factory(),
        )
        self._repository.create_with_audit(evidence, audit)
        self._metric("evidence_lifecycle_total", "upload_requested")
        try:
            upload_url, upload_fields = self._storage.presign_upload(
                bucket_ref=self._bucket_ref,
                object_key=object_key,
                content_type=command.content_type,
                maximum_size=command.declared_size_bytes,
                retention_days=command.retention_days,
                ttl_seconds=60,
            )
        except Exception:
            self._repository.schedule_retry(
                evidence,
                operation="upload",
                error_code="EVIDENCE_STORAGE_UNAVAILABLE",
                changed_at=now,
            )
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None
        return UploadTicket(
            evidence_id=evidence_id,
            expires_at=now + timedelta(seconds=60),
            upload_url=upload_url,
            upload_fields=upload_fields,
        )

    def finalize_upload(
        self,
        evidence_id: UUID,
        context: RequestContext,
    ) -> EvidenceObject:
        now = self._clock()
        evidence = self._owned(evidence_id, context)
        if evidence.state is not EvidenceState.PENDING_UPLOAD:
            raise EvidenceError("EVIDENCE_STATE_CONFLICT")
        object_key, _ = self._protector.reveal(
            evidence_id=evidence.evidence_id,
            tenant_id=evidence.tenant_id,
            object_key_ciphertext=evidence.object_key_ciphertext,
            provider_version_ciphertext=None,
        )
        try:
            facts = self._storage.inspect(
                bucket_ref=evidence.bucket_ref,
                object_key=object_key,
            )
            if facts.object_key != object_key or facts.size_bytes != evidence.size_bytes:
                raise EvidenceError("EVIDENCE_MEDIA_INVALID")
            validate_media(
                header=facts.header,
                declared_content_type=evidence.content_type,
                extension=evidence.original_extension,
                size_bytes=facts.size_bytes,
                expected_kind=evidence.media_kind,
                trusted_width=facts.width,
                trusted_height=facts.height,
                trusted_duration_ms=facts.duration_ms,
            )
            _, version_ciphertext = self._protector.protect(
                evidence_id=evidence.evidence_id,
                tenant_id=evidence.tenant_id,
                object_key=object_key,
                provider_version=facts.provider_version,
            )
            require_transition(evidence.state, EvidenceState.QUARANTINED)
            audit = _audit(
                context=context,
                evidence_id=evidence.evidence_id,
                action="EVIDENCE_UPLOAD_FINALIZED",
                result=IntentResult.SUCCESS,
                occurred_at=now,
                source_event_id=self._identifier_factory(),
            )
            updated = self._repository.transition_with_audit(
                evidence,
                target=EvidenceState.QUARANTINED,
                changed_at=now,
                audit=audit,
                provider_version_ciphertext=version_ciphertext,
                facts=facts,
            )
            self._metric("evidence_lifecycle_total", "quarantined")
            return updated
        except EvidenceError:
            raise
        except Exception:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None

    def retry_upload(
        self,
        evidence_id: UUID,
        context: RequestContext,
    ) -> UploadTicket:
        now = self._clock()
        evidence = self._owned(evidence_id, context)
        if (
            evidence.state is not EvidenceState.PENDING_UPLOAD
            or not context.actor_authenticated
            or evidence.retention_expires_at <= now
        ):
            raise EvidenceError("EVIDENCE_NOT_FOUND")
        object_key, _ = self._protector.reveal(
            evidence_id=evidence.evidence_id,
            tenant_id=evidence.tenant_id,
            object_key_ciphertext=evidence.object_key_ciphertext,
            provider_version_ciphertext=None,
        )
        try:
            upload_url, upload_fields = self._storage.presign_upload(
                bucket_ref=evidence.bucket_ref,
                object_key=object_key,
                content_type=evidence.content_type,
                maximum_size=evidence.size_bytes,
                retention_days=evidence.retention_days,
                ttl_seconds=60,
            )
        except Exception:
            self._repository.schedule_retry(
                evidence,
                operation="upload",
                error_code="EVIDENCE_STORAGE_UNAVAILABLE",
                changed_at=now,
            )
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None
        return UploadTicket(
            evidence_id=evidence.evidence_id,
            expires_at=now + timedelta(seconds=60),
            upload_url=upload_url,
            upload_fields=upload_fields,
        )

    def record_scan_result(
        self,
        evidence_id: UUID,
        *,
        clean: bool,
        context: RequestContext,
    ) -> EvidenceObject:
        now = self._clock()
        evidence = self._owned(evidence_id, context)
        if evidence.state is not EvidenceState.QUARANTINED:
            raise EvidenceError("EVIDENCE_STATE_CONFLICT")
        target = EvidenceState.AVAILABLE if clean else EvidenceState.FAILED
        require_transition(evidence.state, target)
        action = "EVIDENCE_UPLOAD_FINALIZED" if clean else "EVIDENCE_UPLOAD_REJECTED"
        audit = _audit(
            context=context,
            evidence_id=evidence.evidence_id,
            action=action,
            result=IntentResult.SUCCESS if clean else IntentResult.DENIED,
            reason_code=None if clean else "EVIDENCE_SCAN_REJECTED",
            occurred_at=now,
            source_event_id=self._identifier_factory(),
        )
        updated = self._repository.transition_with_audit(
            replace(
                evidence,
                scan_state=ScanState.CLEAN if clean else ScanState.REJECTED,
            ),
            target=target,
            changed_at=now,
            audit=audit,
        )
        self._metric("evidence_lifecycle_total", "available" if clean else "rejected")
        return updated

    def link(
        self,
        evidence_id: UUID,
        link: EvidenceLink,
        *,
        event_type: str,
        resulting_sequence_count: int,
        context: RequestContext,
    ) -> None:
        now = self._clock()
        evidence = self._owned(evidence_id, context)
        if (
            evidence.state is not EvidenceState.AVAILABLE
            or link.evidence_id != evidence.evidence_id
            or link.tenant_id != context.tenant_id
            or link.school_id != context.school_id
            or link.sequence_index >= resulting_sequence_count
        ):
            raise EvidenceError("EVIDENCE_LINK_INVALID")
        validate_selection(event_type, resulting_sequence_count)
        audit = _audit(
            context=context,
            evidence_id=evidence.evidence_id,
            action="EVIDENCE_UPLOAD_FINALIZED",
            result=IntentResult.SUCCESS,
            occurred_at=now,
            source_event_id=self._identifier_factory(),
        )
        self._repository.add_link_with_audit(evidence, link, audit)

    def record_selection_outcome(
        self,
        *,
        event_type: str,
        evidence_count: int,
        manual_override: bool = False,
    ) -> None:
        if manual_override:
            raise EvidenceError("EVIDENCE_MANUAL_OVERRIDE_DISABLED")
        validate_selection(event_type, evidence_count)
        self._metric(
            "evidence_attachment_ratio_events_total",
            "attached" if evidence_count > 0 else "unattached",
        )

    def grant_access(
        self,
        request: AccessRequest,
        context: RequestContext,
    ) -> AccessGrant:
        now = self._clock()
        evidence = self._repository.get(
            request.evidence_id,
            tenant_id=context.tenant_id,
            school_id=context.school_id,
        )
        granted_action, denied_action = audit_actions(request.action)
        if evidence is None or not context.actor_authenticated:
            self._record_denial(
                context=context,
                evidence_id=request.evidence_id,
                action=denied_action,
                reason_code="EVIDENCE_NOT_FOUND",
                occurred_at=now,
            )
            self._metric("evidence_access_total", "denied")
            raise EvidenceError("EVIDENCE_NOT_FOUND")
        try:
            assert_access_preconditions(
                evidence=evidence,
                action=request.action,
                consent_state=request.consent_state,
                reason_code=request.reason_code,
                approval_status=request.approval_status,
                recipient_control_code=request.recipient_control_code,
                activation=self._activation,
                now=now,
            )
            if not self._authorization.authorize(
                context=context,
                evidence=evidence,
                action=request.action,
                consent_state=request.consent_state,
                approval_status=request.approval_status,
            ):
                raise EvidenceError("EVIDENCE_NOT_FOUND")
            ttl = access_ttl(request.action, request.ttl_seconds)
            if request.action is AccessAction.VIEW_METADATA:
                signed_url = None
            else:
                object_key, provider_version = self._protector.reveal(
                    evidence_id=evidence.evidence_id,
                    tenant_id=evidence.tenant_id,
                    object_key_ciphertext=evidence.object_key_ciphertext,
                    provider_version_ciphertext=evidence.provider_version_ciphertext,
                )
                signed_url = self._storage.presign_get(
                    bucket_ref=evidence.bucket_ref,
                    object_key=object_key,
                    provider_version=provider_version,
                    response_disposition=(
                        "attachment"
                        if request.action in {AccessAction.DOWNLOAD, AccessAction.EXPORT}
                        else "inline"
                    ),
                    ttl_seconds=ttl,
                )
            audit = _audit(
                context=context,
                evidence_id=evidence.evidence_id,
                action=granted_action,
                result=IntentResult.SUCCESS,
                reason_code=request.reason_code,
                occurred_at=now,
                source_event_id=self._identifier_factory(),
            )
            self._repository.append_audit(audit)
            self._metric("evidence_access_total", "granted")
            return AccessGrant(
                evidence_id=evidence.evidence_id,
                action=request.action,
                expires_at=now + timedelta(seconds=ttl),
                signed_url=signed_url,
            )
        except EvidenceError as exc:
            self._record_denial(
                context=context,
                evidence_id=evidence.evidence_id,
                action=denied_action,
                reason_code=exc.code,
                occurred_at=now,
            )
            self._metric(
                "evidence_access_total",
                (
                    "url_issue_failed"
                    if exc.code == "EVIDENCE_URL_ISSUE_FAILED"
                    else (
                        "unavailable"
                        if exc.code
                        in {"EVIDENCE_ACCESS_UNAVAILABLE", "EVIDENCE_STORAGE_UNAVAILABLE"}
                        else "denied"
                    )
                ),
            )
            if exc.code in {
                "EVIDENCE_ACCESS_UNAVAILABLE",
                "EVIDENCE_STORAGE_UNAVAILABLE",
                "EVIDENCE_URL_ISSUE_FAILED",
            }:
                raise
            if exc.code == "EVIDENCE_ACCESS_INVALID":
                raise
            raise EvidenceError("EVIDENCE_NOT_FOUND") from None
        except Exception:
            self._record_denial(
                context=context,
                evidence_id=evidence.evidence_id,
                action=denied_action,
                reason_code="EVIDENCE_ACCESS_UNAVAILABLE",
                occurred_at=now,
            )
            self._metric("evidence_access_total", "unavailable")
            raise EvidenceError("EVIDENCE_ACCESS_UNAVAILABLE") from None

    def delete(
        self,
        evidence_id: UUID,
        context: RequestContext,
        *,
        consent_state: ConsentState,
        approval_status: str,
        reason_code: str,
        deletion_job_ref: UUID,
    ) -> EvidenceObject:
        now = self._clock()
        evidence = self._owned(evidence_id, context)
        if (
            not self._activation.active
            or not context.actor_authenticated
            or "evidence.delete_request" not in context.actor_permission_codes
            or context.purpose_code not in {"retention_management", "data_subject_request"}
            or consent_state not in {ConsentState.ALLOWED, ConsentState.NOT_REQUIRED}
            or approval_status != "approved"
            or reason_code not in {"RETENTION_EXPIRED", "DATA_SUBJECT_REQUEST"}
            or (
                reason_code == "RETENTION_EXPIRED"
                and (
                    context.purpose_code != "retention_management"
                    or evidence.retention_expires_at > now
                )
            )
            or (
                reason_code == "DATA_SUBJECT_REQUEST"
                and context.purpose_code != "data_subject_request"
            )
        ):
            self._repository.append_audit(
                _audit(
                    context=context,
                    evidence_id=evidence.evidence_id,
                    action="EVIDENCE_DELETE_FAILED",
                    result=IntentResult.FAILED,
                    reason_code="EVIDENCE_DELETE_DENIED",
                    occurred_at=now,
                    source_event_id=self._identifier_factory(),
                )
            )
            raise EvidenceError("EVIDENCE_NOT_FOUND")
        if evidence.legal_hold_state is LegalHoldState.ACTIVE:
            raise EvidenceError("EVIDENCE_LEGAL_HOLD_ACTIVE")
        require_transition(evidence.state, EvidenceState.DELETE_PENDING)
        pending = self._repository.transition_with_audit(
            evidence,
            target=EvidenceState.DELETE_PENDING,
            changed_at=now,
            audit=_audit(
                context=context,
                evidence_id=evidence.evidence_id,
                action="EVIDENCE_DELETE_REQUESTED",
                result=IntentResult.SUCCESS,
                occurred_at=now,
                source_event_id=self._identifier_factory(),
            ),
            deletion_reason_code=reason_code,
            deletion_job_ref=deletion_job_ref,
            deletion_request_id=context.request_id,
            deletion_correlation_id=context.correlation_id,
        )
        self._metric("evidence_lifecycle_total", "delete_requested")
        object_key, provider_version = self._protector.reveal(
            evidence_id=pending.evidence_id,
            tenant_id=pending.tenant_id,
            object_key_ciphertext=pending.object_key_ciphertext,
            provider_version_ciphertext=pending.provider_version_ciphertext,
        )
        try:
            self._storage.delete(
                bucket_ref=pending.bucket_ref,
                object_key=object_key,
                provider_version=provider_version,
            )
            deleted = self._repository.transition_with_audit(
                pending,
                target=EvidenceState.DELETED,
                changed_at=now,
                audit=_audit(
                    context=context,
                    evidence_id=pending.evidence_id,
                    action="EVIDENCE_DELETE_COMPLETED",
                    result=IntentResult.SUCCESS,
                    occurred_at=now,
                    source_event_id=self._identifier_factory(),
                ),
                deletion_reason_code=pending.deletion_reason_code,
                deletion_job_ref=pending.deletion_job_ref,
                deletion_request_id=pending.deletion_request_id,
                deletion_correlation_id=pending.deletion_correlation_id,
            )
            self._metric("evidence_lifecycle_total", "deleted")
            return deleted
        except Exception:
            self._repository.schedule_retry(
                pending,
                operation="delete",
                error_code="EVIDENCE_STORAGE_UNAVAILABLE",
                changed_at=now,
            )
            self._repository.append_audit(
                _audit(
                    context=context,
                    evidence_id=pending.evidence_id,
                    action="EVIDENCE_DELETE_FAILED",
                    result=IntentResult.FAILED,
                    reason_code="EVIDENCE_STORAGE_UNAVAILABLE",
                    occurred_at=now,
                    source_event_id=self._identifier_factory(),
                )
            )
            self._metric("evidence_lifecycle_total", "delete_failed")
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None

    def reconcile(
        self,
        evidence_id: UUID,
        context: RequestContext,
    ) -> EvidenceObject:
        now = self._clock()
        evidence = self._owned(evidence_id, context)
        if evidence.state in {EvidenceState.DELETED, EvidenceState.DELETE_PENDING}:
            raise EvidenceError("EVIDENCE_STATE_CONFLICT")
        object_key, provider_version = self._protector.reveal(
            evidence_id=evidence.evidence_id,
            tenant_id=evidence.tenant_id,
            object_key_ciphertext=evidence.object_key_ciphertext,
            provider_version_ciphertext=evidence.provider_version_ciphertext,
        )
        matched = False
        reason_code: str | None = None
        try:
            facts = self._storage.inspect(
                bucket_ref=evidence.bucket_ref,
                object_key=object_key,
            )
            matched = (
                facts.object_key == object_key
                and provider_version == facts.provider_version
                and evidence.sha256 == facts.sha256
                and evidence.size_bytes == facts.size_bytes
                and evidence.content_type == facts.content_type
            )
            if not matched:
                reason_code = "EVIDENCE_RECONCILIATION_MISMATCH"
        except EvidenceError as exc:
            if exc.code != "EVIDENCE_OBJECT_MISSING":
                self._repository.schedule_retry(
                    evidence,
                    operation="reconciliation",
                    error_code=exc.code,
                    changed_at=now,
                )
                self._metric("evidence_reconciliation_total", "unavailable")
                raise
            reason_code = "EVIDENCE_OBJECT_MISSING"
        if not matched:
            require_transition(evidence.state, EvidenceState.MISSING)
        audit = _audit(
            context=context,
            evidence_id=evidence.evidence_id,
            action="EVIDENCE_ORPHAN_RECONCILED",
            result=IntentResult.SUCCESS,
            reason_code=reason_code,
            occurred_at=now,
            source_event_id=self._identifier_factory(),
        )
        reconciled = self._repository.reconcile_with_audit(
            evidence,
            matched=matched,
            changed_at=now,
            audit=audit,
        )
        self._metric(
            "evidence_reconciliation_total",
            "matched"
            if matched
            else ("missing" if reason_code == "EVIDENCE_OBJECT_MISSING" else "mismatch"),
        )
        return reconciled

    def _owned(self, evidence_id: UUID, context: RequestContext) -> EvidenceObject:
        evidence = self._repository.get(
            evidence_id,
            tenant_id=context.tenant_id,
            school_id=context.school_id,
        )
        if evidence is None:
            raise EvidenceError("EVIDENCE_NOT_FOUND")
        return evidence

    def _record_denial(
        self,
        *,
        context: RequestContext,
        evidence_id: UUID,
        action: str,
        reason_code: str,
        occurred_at: datetime,
    ) -> None:
        try:
            self._repository.append_audit(
                _audit(
                    context=context,
                    evidence_id=evidence_id,
                    action=action,
                    result=IntentResult.DENIED,
                    reason_code=reason_code,
                    occurred_at=occurred_at,
                    source_event_id=self._identifier_factory(),
                )
            )
        except Exception:
            raise EvidenceError("EVIDENCE_ACCESS_UNAVAILABLE") from None

    def _metric(self, metric: str, outcome: str) -> None:
        with suppress(Exception):
            self._metrics.increment(metric, outcome=outcome)
