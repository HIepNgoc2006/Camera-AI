from __future__ import annotations

import struct
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from audit_log_service.domain.policies import ACTION_POLICIES
from camera_ai_audit import AuditIntent
from evidence_service.application.service import EvidenceApplicationService
from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.models import (
    AccessAction,
    AccessRequest,
    ConsentState,
    EvidenceLink,
    EvidenceObject,
    EvidenceState,
    MediaKind,
    RequestContext,
    ScanState,
    StoredObjectFacts,
    UploadCommand,
)
from evidence_service.domain.policies import PolicyActivation, permission_for

NOW = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
TENANT_ID = UUID("00000000-0000-4000-8000-000000006711")
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000006712")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000006713")
EVENT_ID = UUID("00000000-0000-4000-8000-000000006714")
RESOURCE_ID = UUID("00000000-0000-4000-8000-000000006715")


class SequenceIdentifiers:
    def __init__(self) -> None:
        self._next = 0x6720

    def __call__(self) -> UUID:
        self._next += 1
        return UUID(f"00000000-0000-4000-8000-{self._next:012x}")


class FakeProtector:
    def protect(
        self,
        *,
        evidence_id: UUID,
        tenant_id: UUID,
        object_key: str,
        provider_version: str | None,
    ) -> tuple[bytes, bytes | None]:
        del evidence_id, tenant_id
        return (
            b"ENCV1|" + object_key.encode(),
            None if provider_version is None else b"ENCV1|" + provider_version.encode(),
        )

    def reveal(
        self,
        *,
        evidence_id: UUID,
        tenant_id: UUID,
        object_key_ciphertext: bytes,
        provider_version_ciphertext: bytes | None,
    ) -> tuple[str, str | None]:
        del evidence_id, tenant_id
        return (
            object_key_ciphertext.removeprefix(b"ENCV1|").decode(),
            (
                None
                if provider_version_ciphertext is None
                else provider_version_ciphertext.removeprefix(b"ENCV1|").decode()
            ),
        )

    def key_version(self, ciphertext: bytes) -> str:
        del ciphertext
        return "synthetic-kek-v1"


class FakeAuthorization:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    def authorize(
        self,
        *,
        context: RequestContext,
        evidence: EvidenceObject,
        action: AccessAction,
        consent_state: ConsentState,
        approval_status: str,
    ) -> bool:
        del evidence, consent_state, approval_status
        return self.allowed and permission_for(action) in context.actor_permission_codes


class FakeMetrics:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def increment(self, metric: str, *, outcome: str) -> None:
        self.events.append((metric, outcome))

    def observe(self, metric: str, *, seconds: float) -> None:
        del metric, seconds

    def set_gauge(self, metric: str, *, value: float) -> None:
        del metric, value


class MemoryRepository:
    def __init__(self) -> None:
        self.objects: dict[UUID, EvidenceObject] = {}
        self.audits: list[AuditIntent] = []
        self.links: list[EvidenceLink] = []
        self.retries: list[tuple[UUID, str, str]] = []

    def create_with_audit(self, evidence: EvidenceObject, audit: AuditIntent) -> None:
        self.objects[evidence.evidence_id] = evidence
        self.audits.append(audit)

    def get(
        self,
        evidence_id: UUID,
        *,
        tenant_id: UUID,
        school_id: UUID,
    ) -> EvidenceObject | None:
        evidence = self.objects.get(evidence_id)
        if evidence is None or evidence.tenant_id != tenant_id or evidence.school_id != school_id:
            return None
        return evidence

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
    ) -> EvidenceObject:
        updated = replace(
            evidence,
            state=target,
            updated_at=changed_at,
            row_version=evidence.row_version + 1,
            provider_version_ciphertext=(
                evidence.provider_version_ciphertext
                if provider_version_ciphertext is None
                else provider_version_ciphertext
            ),
            sha256=evidence.sha256 if facts is None else facts.sha256,
            size_bytes=evidence.size_bytes if facts is None else facts.size_bytes,
            width=evidence.width if facts is None else facts.width,
            height=evidence.height if facts is None else facts.height,
            duration_ms=evidence.duration_ms if facts is None else facts.duration_ms,
            deleted_at=changed_at if target is EvidenceState.DELETED else evidence.deleted_at,
            deletion_reason_code=(
                evidence.deletion_reason_code
                if deletion_reason_code is None
                else deletion_reason_code
            ),
            deletion_job_ref=(
                evidence.deletion_job_ref if deletion_job_ref is None else deletion_job_ref
            ),
            deletion_request_id=(
                evidence.deletion_request_id if deletion_request_id is None else deletion_request_id
            ),
            deletion_correlation_id=(
                evidence.deletion_correlation_id
                if deletion_correlation_id is None
                else deletion_correlation_id
            ),
        )
        self.objects[evidence.evidence_id] = updated
        self.audits.append(audit)
        return updated

    def add_link_with_audit(
        self,
        evidence: EvidenceObject,
        link: EvidenceLink,
        audit: AuditIntent,
    ) -> None:
        del evidence
        self.links.append(link)
        self.audits.append(audit)

    def reconcile_with_audit(
        self,
        evidence: EvidenceObject,
        *,
        matched: bool,
        changed_at: datetime,
        audit: AuditIntent,
    ) -> EvidenceObject:
        updated = replace(
            evidence,
            state=evidence.state if matched else EvidenceState.MISSING,
            updated_at=changed_at,
            row_version=evidence.row_version + 1,
        )
        self.objects[evidence.evidence_id] = updated
        self.audits.append(audit)
        return updated

    def append_audit(self, audit: AuditIntent) -> None:
        self.audits.append(audit)

    def schedule_retry(
        self,
        evidence: EvidenceObject,
        *,
        operation: str,
        error_code: str,
        changed_at: datetime,
    ) -> None:
        del changed_at
        self.retries.append((evidence.evidence_id, operation, error_code))


class FakeStorage:
    def __init__(self) -> None:
        self.object_key = ""
        self.deleted = False
        self.fail_upload = False
        self.fail_inspect = False
        self.fail_delete = False

    def presign_upload(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        content_type: str,
        maximum_size: int,
        retention_days: int,
        ttl_seconds: int,
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        del bucket_ref, maximum_size, retention_days, ttl_seconds
        if self.fail_upload:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE")
        self.object_key = object_key
        return (
            "https://private.invalid/upload?synthetic=redacted",
            (("Content-Type", content_type), ("key", object_key)),
        )

    def inspect(
        self,
        *,
        bucket_ref: str,
        object_key: str,
    ) -> StoredObjectFacts:
        del bucket_ref
        if self.fail_inspect:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE")
        header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 640, 480)
        return StoredObjectFacts(
            object_key=object_key,
            provider_version="synthetic-version-1",
            size_bytes=1024,
            sha256="a" * 64,
            content_type="image/png",
            header=header,
            width=640,
            height=480,
            duration_ms=None,
        )

    def presign_get(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        provider_version: str | None,
        response_disposition: str,
        ttl_seconds: int,
    ) -> str:
        del bucket_ref, object_key, provider_version, response_disposition, ttl_seconds
        return "https://private.invalid/get?synthetic=redacted"

    def delete(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        provider_version: str | None,
    ) -> None:
        del bucket_ref, object_key, provider_version
        if self.fail_delete:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE")
        self.deleted = True


def context(
    *,
    tenant_id: UUID = TENANT_ID,
    school_id: UUID = SCHOOL_ID,
    permission_codes: frozenset[str] | None = None,
    purpose_code: str = "student_attendance",
) -> RequestContext:
    return RequestContext(
        actor_id=ACTOR_ID,
        tenant_id=tenant_id,
        school_id=school_id,
        request_id="req_671111111111",
        correlation_id="cor_671111111111",
        purpose_code=purpose_code,
        actor_authenticated=True,
        actor_permission_codes=permission_codes
        or frozenset(
            {
                "evidence.view_metadata",
                "evidence.view_original",
                "evidence.download",
            }
        ),
    )


def service(
    *,
    activation: PolicyActivation | None = None,
    authorization: FakeAuthorization | None = None,
    metrics: FakeMetrics | None = None,
) -> tuple[EvidenceApplicationService, MemoryRepository, FakeStorage]:
    repository = MemoryRepository()
    storage = FakeStorage()
    return (
        EvidenceApplicationService(
            repository,
            storage,
            FakeProtector(),
            authorization or FakeAuthorization(),
            activation=activation,
            metrics=metrics,
            clock=lambda: NOW,
            identifier_factory=SequenceIdentifiers(),
        ),
        repository,
        storage,
    )


def upload_command() -> UploadCommand:
    return UploadCommand(
        source_event_id=EVENT_ID,
        camera_id=None,
        task_id=None,
        captured_at=NOW - timedelta(seconds=1),
        media_kind=MediaKind.IMAGE,
        content_type="image/png",
        original_extension=".png",
        declared_size_bytes=1024,
        sensitivity="critical",
        retention_policy_version="attendance_retention_v1",
        retention_days=30,
        retention_expires_at=NOW + timedelta(days=30),
    )


def available_evidence(
    app: EvidenceApplicationService,
    ctx: RequestContext,
) -> EvidenceObject:
    ticket = app.request_upload(upload_command(), ctx)
    quarantined = app.finalize_upload(ticket.evidence_id, ctx)
    assert quarantined.state is EvidenceState.QUARANTINED
    return app.record_scan_result(ticket.evidence_id, clean=True, context=ctx)


def active_policy() -> PolicyActivation:
    return PolicyActivation(
        privacy_legal_approved=True,
        security_ops_approved=True,
        business_owner_approved=True,
    )


def test_upload_finalize_scan_link_access_and_delete_are_audited() -> None:
    metrics = FakeMetrics()
    app, repository, storage = service(activation=active_policy(), metrics=metrics)
    ctx = context()
    evidence = available_evidence(app, ctx)
    assert evidence.state is EvidenceState.AVAILABLE
    assert evidence.scan_state is ScanState.CLEAN
    assert evidence.sha256 == "a" * 64

    link = EvidenceLink(
        link_id=UUID("00000000-0000-4000-8000-000000006716"),
        evidence_id=evidence.evidence_id,
        tenant_id=TENANT_ID,
        school_id=SCHOOL_ID,
        resource_type="attendance_record",
        resource_id=RESOURCE_ID,
        link_purpose="first_seen",
        sequence_role="first",
        sequence_index=0,
        selection_policy_version="evidence_selection_policy_v1",
        linked_at=NOW,
    )
    app.link(
        evidence.evidence_id,
        link,
        event_type="student_attendance",
        resulting_sequence_count=1,
        context=ctx,
    )
    app.record_selection_outcome(event_type="student_attendance", evidence_count=1)

    grant = app.grant_access(
        AccessRequest(
            evidence_id=evidence.evidence_id,
            action=AccessAction.VIEW_ORIGINAL,
            ttl_seconds=None,
            consent_state=ConsentState.ALLOWED,
            reason_code="ATTENDANCE_AUDIT",
        ),
        ctx,
    )
    assert grant.expires_at == NOW + timedelta(seconds=60)
    assert grant.signed_url == "https://private.invalid/get?synthetic=redacted"
    assert "synthetic=redacted" not in repr(grant)
    assert repository.audits[-1].reason_code == "ATTENDANCE_AUDIT"

    delete_context = context(
        permission_codes=ctx.actor_permission_codes | {"evidence.delete_request"},
        purpose_code="data_subject_request",
    )
    deleted = app.delete(
        evidence.evidence_id,
        delete_context,
        consent_state=ConsentState.NOT_REQUIRED,
        approval_status="approved",
        reason_code="DATA_SUBJECT_REQUEST",
        deletion_job_ref=UUID("00000000-0000-4000-8000-000000006717"),
    )
    assert deleted.state is EvidenceState.DELETED
    assert storage.deleted is True
    actions = [audit.action for audit in repository.audits]
    assert actions == [
        "EVIDENCE_UPLOAD_REQUESTED",
        "EVIDENCE_UPLOAD_FINALIZED",
        "EVIDENCE_UPLOAD_FINALIZED",
        "EVIDENCE_UPLOAD_FINALIZED",
        "EVIDENCE_VIEW_GRANTED",
        "EVIDENCE_DELETE_REQUESTED",
        "EVIDENCE_DELETE_COMPLETED",
    ]
    for audit in repository.audits:
        policy = ACTION_POLICIES[audit.action]
        assert audit.source_service in policy.publishers
        assert audit.resource_type in policy.resource_types
        assert audit.result.value in {result.value for result in policy.results}
        assert {name for name, _ in audit.policy_versions} <= policy.policy_types
    assert metrics.events == [
        ("evidence_lifecycle_total", "upload_requested"),
        ("evidence_lifecycle_total", "quarantined"),
        ("evidence_lifecycle_total", "available"),
        ("evidence_attachment_ratio_events_total", "attached"),
        ("evidence_access_total", "granted"),
        ("evidence_lifecycle_total", "delete_requested"),
        ("evidence_lifecycle_total", "deleted"),
    ]


def test_policy_is_inactive_by_default_and_denial_is_audited() -> None:
    app, repository, _ = service()
    ctx = context()
    evidence = available_evidence(app, ctx)

    with pytest.raises(EvidenceError, match="EVIDENCE_ACCESS_UNAVAILABLE"):
        app.grant_access(
            AccessRequest(
                evidence_id=evidence.evidence_id,
                action=AccessAction.VIEW_METADATA,
                ttl_seconds=None,
                consent_state=ConsentState.ALLOWED,
            ),
            ctx,
        )
    assert repository.audits[-1].action == "EVIDENCE_VIEW_DENIED"
    assert repository.audits[-1].reason_code == "EVIDENCE_ACCESS_UNAVAILABLE"


def test_attachment_ratio_counts_zero_evidence_and_manual_override_stays_disabled() -> None:
    metrics = FakeMetrics()
    app, _, _ = service(metrics=metrics)
    app.record_selection_outcome(event_type="emotion_insight", evidence_count=0)
    assert metrics.events == [("evidence_attachment_ratio_events_total", "unattached")]
    with pytest.raises(EvidenceError, match="EVIDENCE_MANUAL_OVERRIDE_DISABLED"):
        app.record_selection_outcome(
            event_type="student_attendance",
            evidence_count=5,
            manual_override=True,
        )
    with pytest.raises(EvidenceError, match="EVIDENCE_SELECTION_INVALID"):
        app.record_selection_outcome(
            event_type="student_attendance",
            evidence_count=5,
        )


def test_reconciliation_matches_exact_version_checksum_and_marks_mismatch_missing() -> None:
    app, repository, _ = service(activation=active_policy())
    ctx = context()
    evidence = available_evidence(app, ctx)

    matched = app.reconcile(evidence.evidence_id, ctx)
    assert matched.state is EvidenceState.AVAILABLE
    assert repository.audits[-1].action == "EVIDENCE_ORPHAN_RECONCILED"
    assert repository.audits[-1].result.value == "success"

    repository.objects[evidence.evidence_id] = replace(
        matched,
        sha256="b" * 64,
    )
    missing = app.reconcile(evidence.evidence_id, ctx)
    assert missing.state is EvidenceState.MISSING
    assert repository.audits[-1].result.value == "success"
    assert repository.audits[-1].reason_code == "EVIDENCE_RECONCILIATION_MISMATCH"


def test_missing_cross_tenant_and_denied_are_publicly_indistinguishable() -> None:
    app, repository, _ = service(
        activation=active_policy(),
        authorization=FakeAuthorization(allowed=False),
    )
    ctx = context()
    evidence = available_evidence(app, ctx)
    request = AccessRequest(
        evidence_id=evidence.evidence_id,
        action=AccessAction.VIEW_METADATA,
        ttl_seconds=None,
        consent_state=ConsentState.ALLOWED,
    )

    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(request, ctx)
    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(
            request,
            context(tenant_id=UUID("00000000-0000-4000-8000-000000006799")),
        )
    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(
            request,
            context(school_id=UUID("00000000-0000-4000-8000-000000006798")),
        )
    assert [audit.action for audit in repository.audits[-3:]] == [
        "EVIDENCE_VIEW_DENIED",
        "EVIDENCE_VIEW_DENIED",
        "EVIDENCE_VIEW_DENIED",
    ]


def test_export_requires_dual_control_recipient_control_and_separate_permission() -> None:
    app, repository, _ = service(activation=active_policy())
    ctx = context()
    evidence = available_evidence(app, ctx)
    base_request = AccessRequest(
        evidence_id=evidence.evidence_id,
        action=AccessAction.EXPORT,
        ttl_seconds=120,
        consent_state=ConsentState.ALLOWED,
        reason_code="ATTENDANCE_AUDIT",
    )

    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(base_request, ctx)
    assert repository.audits[-1].action == "EVIDENCE_EXPORT_DENIED"
    assert repository.audits[-1].reason_code == "EVIDENCE_EXPORT_APPROVAL_REQUIRED"

    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(replace(base_request, approval_status="approved"), ctx)
    assert repository.audits[-1].reason_code == "EVIDENCE_EXPORT_RECIPIENT_INVALID"

    approved_request = replace(
        base_request,
        approval_status="approved",
        recipient_control_code="authenticated_requester",
    )
    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(approved_request, ctx)
    assert repository.audits[-1].reason_code == "EVIDENCE_NOT_FOUND"

    export_context = context(
        permission_codes=frozenset(
            {
                "evidence.view_metadata",
                "evidence.view_original",
                "evidence.download",
                "evidence.export",
            }
        )
    )
    grant = app.grant_access(approved_request, export_context)
    assert grant.expires_at == NOW + timedelta(seconds=120)
    assert repository.audits[-1].action == "EVIDENCE_EXPORT_GRANTED"


@pytest.mark.parametrize(
    ("action", "reason_code", "approval_status", "recipient_control_code", "audit_action"),
    [
        (AccessAction.VIEW_THUMBNAIL, None, "not_required", None, "EVIDENCE_VIEW_DENIED"),
        (
            AccessAction.VIEW_ORIGINAL,
            "ATTENDANCE_AUDIT",
            "not_required",
            None,
            "EVIDENCE_VIEW_DENIED",
        ),
        (
            AccessAction.DOWNLOAD,
            "ATTENDANCE_AUDIT",
            "not_required",
            None,
            "EVIDENCE_VIEW_DENIED",
        ),
        (
            AccessAction.EXPORT,
            "ATTENDANCE_AUDIT",
            "approved",
            "authenticated_requester",
            "EVIDENCE_EXPORT_DENIED",
        ),
    ],
)
def test_each_media_action_requires_its_own_permission(
    action: AccessAction,
    reason_code: str | None,
    approval_status: str,
    recipient_control_code: str | None,
    audit_action: str,
) -> None:
    app, repository, _ = service(activation=active_policy())
    ctx = context(permission_codes=frozenset({"evidence.view_metadata"}))
    evidence = available_evidence(app, ctx)

    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(
            AccessRequest(
                evidence_id=evidence.evidence_id,
                action=action,
                ttl_seconds=60,
                consent_state=ConsentState.ALLOWED,
                reason_code=reason_code,
                approval_status=approval_status,
                recipient_control_code=recipient_control_code,
            ),
            ctx,
        )
    assert repository.audits[-1].action == audit_action


def test_delete_requires_active_policy_permission_purpose_consent_and_approval() -> None:
    app, repository, _ = service(activation=active_policy())
    ctx = context()
    evidence = available_evidence(app, ctx)

    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.delete(
            evidence.evidence_id,
            ctx,
            consent_state=ConsentState.ALLOWED,
            approval_status="approved",
            reason_code="RETENTION_EXPIRED",
            deletion_job_ref=UUID("00000000-0000-4000-8000-000000006718"),
        )
    assert repository.audits[-1].action == "EVIDENCE_DELETE_FAILED"
    assert repository.audits[-1].reason_code == "EVIDENCE_DELETE_DENIED"


def test_cross_store_failures_schedule_bounded_retry_without_claiming_atomicity() -> None:
    app, repository, storage = service(activation=active_policy())
    ctx = context()
    storage.fail_upload = True
    with pytest.raises(EvidenceError, match="EVIDENCE_STORAGE_UNAVAILABLE"):
        app.request_upload(upload_command(), ctx)
    assert repository.retries[-1][1:] == ("upload", "EVIDENCE_STORAGE_UNAVAILABLE")

    storage.fail_upload = False
    pending_id = next(iter(repository.objects))
    retry_ticket = app.retry_upload(pending_id, ctx)
    assert retry_ticket.evidence_id == pending_id
    evidence = available_evidence(app, ctx)
    storage.fail_inspect = True
    with pytest.raises(EvidenceError, match="EVIDENCE_STORAGE_UNAVAILABLE"):
        app.reconcile(evidence.evidence_id, ctx)
    assert repository.retries[-1][1:] == (
        "reconciliation",
        "EVIDENCE_STORAGE_UNAVAILABLE",
    )

    storage.fail_inspect = False
    storage.fail_delete = True
    with pytest.raises(EvidenceError, match="EVIDENCE_STORAGE_UNAVAILABLE"):
        app.delete(
            evidence.evidence_id,
            context(
                permission_codes=ctx.actor_permission_codes | {"evidence.delete_request"},
                purpose_code="data_subject_request",
            ),
            consent_state=ConsentState.NOT_REQUIRED,
            approval_status="approved",
            reason_code="DATA_SUBJECT_REQUEST",
            deletion_job_ref=UUID("00000000-0000-4000-8000-000000006720"),
        )
    assert repository.objects[evidence.evidence_id].state is EvidenceState.DELETE_PENDING
    assert repository.retries[-1][1:] == ("delete", "EVIDENCE_STORAGE_UNAVAILABLE")


def test_expired_retention_blocked_consent_and_active_hold_fail_closed() -> None:
    app, repository, _ = service(activation=active_policy())
    ctx = context()
    evidence = available_evidence(app, ctx)
    repository.objects[evidence.evidence_id] = replace(
        evidence,
        captured_at=NOW - timedelta(days=2, seconds=1),
        received_at=NOW - timedelta(days=2),
        created_at=NOW - timedelta(days=2),
        retention_expires_at=NOW - timedelta(days=1),
    )
    request = AccessRequest(
        evidence_id=evidence.evidence_id,
        action=AccessAction.VIEW_METADATA,
        ttl_seconds=None,
        consent_state=ConsentState.ALLOWED,
    )
    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(request, ctx)

    repository.objects[evidence.evidence_id] = evidence
    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        app.grant_access(replace(request, consent_state=ConsentState.BLOCKED), ctx)

    repository.objects[evidence.evidence_id] = replace(
        evidence,
        legal_hold_state=evidence.legal_hold_state.ACTIVE,
    )
    with pytest.raises(EvidenceError, match="EVIDENCE_LEGAL_HOLD_ACTIVE"):
        app.delete(
            evidence.evidence_id,
            context(
                permission_codes=ctx.actor_permission_codes | {"evidence.delete_request"},
                purpose_code="data_subject_request",
            ),
            consent_state=ConsentState.NOT_REQUIRED,
            approval_status="approved",
            reason_code="DATA_SUBJECT_REQUEST",
            deletion_job_ref=UUID("00000000-0000-4000-8000-000000006719"),
        )
