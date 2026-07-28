"""Tenant-scoped PostgreSQL repository with transactional evidence audit outbox."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from camera_ai_audit import AuditIntent
from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from evidence_service.application.ports import EvidenceRepository
from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.models import (
    EvidenceLink,
    EvidenceObject,
    EvidenceState,
    LegalHoldState,
    MediaKind,
    ScanState,
    StoredObjectFacts,
)
from evidence_service.infrastructure.tables import audit_outbox, evidence_links, evidence_objects


def _object_values(evidence: EvidenceObject) -> dict[str, object]:
    return {
        "evidence_id": evidence.evidence_id,
        "tenant_id": evidence.tenant_id,
        "school_id": evidence.school_id,
        "source_event_id": evidence.source_event_id,
        "camera_id": evidence.camera_id,
        "task_id": evidence.task_id,
        "captured_at": evidence.captured_at,
        "received_at": evidence.received_at,
        "object_key_ciphertext": evidence.object_key_ciphertext,
        "bucket_ref": evidence.bucket_ref,
        "provider_version_ciphertext": evidence.provider_version_ciphertext,
        "encryption_key_version_ref": evidence.encryption_key_version_ref,
        "media_kind": evidence.media_kind.value,
        "content_type": evidence.content_type,
        "original_extension": evidence.original_extension,
        "size_bytes": evidence.size_bytes,
        "sha256": evidence.sha256,
        "width": evidence.width,
        "height": evidence.height,
        "duration_ms": evidence.duration_ms,
        "sensitivity": evidence.sensitivity,
        "purpose_code": evidence.purpose_code,
        "state": evidence.state.value,
        "scan_state": evidence.scan_state.value,
        "upload_attempt_count": 0,
        "next_upload_attempt_at": None,
        "last_upload_error_code": None,
        "reconciliation_state": "pending",
        "reconciliation_attempt_count": 0,
        "next_reconciliation_at": None,
        "last_reconciliation_error_code": None,
        "last_reconciled_at": None,
        "retention_policy_version": evidence.retention_policy_version,
        "retention_days": evidence.retention_days,
        "retention_expires_at": evidence.retention_expires_at,
        "legal_hold_state": evidence.legal_hold_state.value,
        "legal_hold_ref": None,
        "created_actor_id": evidence.created_actor_id,
        "created_at": evidence.created_at,
        "updated_at": evidence.updated_at,
        "delete_requested_at": None,
        "delete_attempt_count": 0,
        "next_delete_attempt_at": None,
        "last_delete_error_code": None,
        "deleted_at": evidence.deleted_at,
        "deletion_reason_code": evidence.deletion_reason_code,
        "deletion_job_ref": evidence.deletion_job_ref,
        "deletion_request_id": evidence.deletion_request_id,
        "deletion_correlation_id": evidence.deletion_correlation_id,
        "row_version": evidence.row_version,
    }


def _from_row(row: sa.RowMapping) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=row["evidence_id"],
        tenant_id=row["tenant_id"],
        school_id=row["school_id"],
        source_event_id=row["source_event_id"],
        camera_id=row["camera_id"],
        task_id=row["task_id"],
        captured_at=row["captured_at"],
        received_at=row["received_at"],
        object_key_ciphertext=bytes(row["object_key_ciphertext"]),
        bucket_ref=row["bucket_ref"],
        provider_version_ciphertext=(
            None
            if row["provider_version_ciphertext"] is None
            else bytes(row["provider_version_ciphertext"])
        ),
        encryption_key_version_ref=row["encryption_key_version_ref"],
        media_kind=MediaKind(row["media_kind"]),
        content_type=row["content_type"],
        original_extension=row["original_extension"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        width=row["width"],
        height=row["height"],
        duration_ms=row["duration_ms"],
        sensitivity=row["sensitivity"],
        purpose_code=row["purpose_code"],
        state=EvidenceState(row["state"]),
        scan_state=ScanState(row["scan_state"]),
        retention_policy_version=row["retention_policy_version"],
        retention_days=row["retention_days"],
        retention_expires_at=row["retention_expires_at"],
        legal_hold_state=LegalHoldState(row["legal_hold_state"]),
        created_actor_id=row["created_actor_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        deletion_reason_code=row["deletion_reason_code"],
        deletion_job_ref=row["deletion_job_ref"],
        deletion_request_id=row["deletion_request_id"],
        deletion_correlation_id=row["deletion_correlation_id"],
        row_version=row["row_version"],
    )


def _audit_values(audit: AuditIntent) -> dict[str, object]:
    return {
        "audit_outbox_id": uuid5(
            NAMESPACE_URL,
            f"camera-ai:evidence-audit:{audit.source_service}:{audit.source_event_id}",
        ),
        "source_service": audit.source_service,
        "source_event_id": audit.source_event_id,
        "school_id": audit.school_id,
        "payload": audit.publisher_payload(),
        "publish_status": "pending",
        "attempt_count": 0,
        "next_attempt_at": audit.occurred_at,
        "recorded_at": audit.occurred_at,
        "delivered_at": None,
    }


def _insert_audit(connection: sa.Connection, audit: AuditIntent) -> None:
    connection.execute(
        pg_insert(audit_outbox)
        .values(**_audit_values(audit))
        .on_conflict_do_nothing(index_elements=["source_service", "source_event_id"])
    )


class SqlAlchemyEvidenceRepository(EvidenceRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_with_audit(self, evidence: EvidenceObject, audit: AuditIntent) -> None:
        if (
            audit.resource_id != evidence.evidence_id
            or audit.school_id != evidence.school_id
            or evidence.state is not EvidenceState.PENDING_UPLOAD
        ):
            raise EvidenceError("EVIDENCE_AUTHORITY_DENIED")
        try:
            with self._engine.begin() as connection:
                connection.execute(sa.insert(evidence_objects).values(**_object_values(evidence)))
                _insert_audit(connection, audit)
        except IntegrityError:
            raise EvidenceError("EVIDENCE_CONFLICT") from None
        except SQLAlchemyError:
            raise EvidenceError("EVIDENCE_DATABASE_UNAVAILABLE") from None

    def get(
        self,
        evidence_id: UUID,
        *,
        tenant_id: UUID,
        school_id: UUID,
    ) -> EvidenceObject | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(evidence_objects).where(
                            evidence_objects.c.evidence_id == evidence_id,
                            evidence_objects.c.tenant_id == tenant_id,
                            evidence_objects.c.school_id == school_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return None if row is None else _from_row(row)
        except SQLAlchemyError:
            raise EvidenceError("EVIDENCE_DATABASE_UNAVAILABLE") from None

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
        if audit.resource_id != evidence.evidence_id or audit.school_id != evidence.school_id:
            raise EvidenceError("EVIDENCE_AUTHORITY_DENIED")
        values: dict[str, object] = {
            "state": target.value,
            "scan_state": evidence.scan_state.value,
            "updated_at": changed_at,
            "row_version": evidence.row_version + 1,
        }
        if provider_version_ciphertext is not None:
            values["provider_version_ciphertext"] = provider_version_ciphertext
        if facts is not None:
            values.update(
                {
                    "sha256": facts.sha256,
                    "size_bytes": facts.size_bytes,
                    "width": facts.width,
                    "height": facts.height,
                    "duration_ms": facts.duration_ms,
                    "reconciliation_state": "matched",
                    "last_reconciled_at": changed_at,
                    "next_upload_attempt_at": None,
                    "last_upload_error_code": None,
                }
            )
        if target is EvidenceState.DELETE_PENDING:
            values.update(
                {
                    "delete_requested_at": changed_at,
                    "deletion_reason_code": deletion_reason_code,
                    "deletion_job_ref": deletion_job_ref,
                    "deletion_request_id": deletion_request_id,
                    "deletion_correlation_id": deletion_correlation_id,
                }
            )
        if target is EvidenceState.DELETED:
            values.update(
                {
                    "deleted_at": changed_at,
                    "deletion_reason_code": deletion_reason_code,
                    "deletion_job_ref": deletion_job_ref,
                    "deletion_request_id": deletion_request_id,
                    "deletion_correlation_id": deletion_correlation_id,
                    "next_delete_attempt_at": None,
                    "last_delete_error_code": None,
                }
            )
        try:
            with self._engine.begin() as connection:
                updated = connection.execute(
                    sa.update(evidence_objects)
                    .where(
                        evidence_objects.c.evidence_id == evidence.evidence_id,
                        evidence_objects.c.tenant_id == evidence.tenant_id,
                        evidence_objects.c.school_id == evidence.school_id,
                        evidence_objects.c.row_version == evidence.row_version,
                        evidence_objects.c.state == evidence.state.value,
                    )
                    .values(**values)
                )
                if updated.rowcount != 1:
                    raise EvidenceError("EVIDENCE_STATE_CONFLICT")
                _insert_audit(connection, audit)
                row = (
                    connection.execute(
                        sa.select(evidence_objects).where(
                            evidence_objects.c.evidence_id == evidence.evidence_id
                        )
                    )
                    .mappings()
                    .one()
                )
            return _from_row(row)
        except EvidenceError:
            raise
        except IntegrityError:
            raise EvidenceError("EVIDENCE_CONFLICT") from None
        except SQLAlchemyError:
            raise EvidenceError("EVIDENCE_DATABASE_UNAVAILABLE") from None

    def add_link_with_audit(
        self,
        evidence: EvidenceObject,
        link: EvidenceLink,
        audit: AuditIntent,
    ) -> None:
        if (
            link.evidence_id != evidence.evidence_id
            or link.tenant_id != evidence.tenant_id
            or link.school_id != evidence.school_id
            or audit.resource_id != evidence.evidence_id
        ):
            raise EvidenceError("EVIDENCE_AUTHORITY_DENIED")
        try:
            with self._engine.begin() as connection:
                locked = connection.scalar(
                    sa.select(evidence_objects.c.evidence_id)
                    .where(
                        evidence_objects.c.evidence_id == evidence.evidence_id,
                        evidence_objects.c.tenant_id == evidence.tenant_id,
                        evidence_objects.c.school_id == evidence.school_id,
                        evidence_objects.c.state == EvidenceState.AVAILABLE.value,
                    )
                    .with_for_update()
                )
                if locked is None:
                    raise EvidenceError("EVIDENCE_NOT_AVAILABLE")
                connection.execute(
                    sa.insert(evidence_links).values(
                        link_id=link.link_id,
                        evidence_id=link.evidence_id,
                        tenant_id=link.tenant_id,
                        school_id=link.school_id,
                        resource_type=link.resource_type,
                        resource_id=link.resource_id,
                        link_purpose=link.link_purpose,
                        sequence_role=link.sequence_role,
                        sequence_index=link.sequence_index,
                        selection_policy_version=link.selection_policy_version,
                        linked_at=link.linked_at,
                    )
                )
                _insert_audit(connection, audit)
        except EvidenceError:
            raise
        except IntegrityError:
            raise EvidenceError("EVIDENCE_LINK_CONFLICT") from None
        except SQLAlchemyError:
            raise EvidenceError("EVIDENCE_DATABASE_UNAVAILABLE") from None

    def reconcile_with_audit(
        self,
        evidence: EvidenceObject,
        *,
        matched: bool,
        changed_at: datetime,
        audit: AuditIntent,
    ) -> EvidenceObject:
        if audit.resource_id != evidence.evidence_id or audit.school_id != evidence.school_id:
            raise EvidenceError("EVIDENCE_AUTHORITY_DENIED")
        values: dict[str, object] = {
            "reconciliation_state": "matched" if matched else "missing",
            "last_reconciled_at": changed_at,
            "next_reconciliation_at": None,
            "last_reconciliation_error_code": None,
            "updated_at": changed_at,
            "row_version": evidence.row_version + 1,
        }
        if not matched:
            values["state"] = EvidenceState.MISSING.value
        try:
            with self._engine.begin() as connection:
                updated = connection.execute(
                    sa.update(evidence_objects)
                    .where(
                        evidence_objects.c.evidence_id == evidence.evidence_id,
                        evidence_objects.c.tenant_id == evidence.tenant_id,
                        evidence_objects.c.school_id == evidence.school_id,
                        evidence_objects.c.row_version == evidence.row_version,
                        evidence_objects.c.state == evidence.state.value,
                    )
                    .values(**values)
                )
                if updated.rowcount != 1:
                    raise EvidenceError("EVIDENCE_STATE_CONFLICT")
                _insert_audit(connection, audit)
                row = (
                    connection.execute(
                        sa.select(evidence_objects).where(
                            evidence_objects.c.evidence_id == evidence.evidence_id
                        )
                    )
                    .mappings()
                    .one()
                )
            return _from_row(row)
        except EvidenceError:
            raise
        except SQLAlchemyError:
            raise EvidenceError("EVIDENCE_DATABASE_UNAVAILABLE") from None

    def append_audit(self, audit: AuditIntent) -> None:
        try:
            with self._engine.begin() as connection:
                _insert_audit(connection, audit)
        except SQLAlchemyError:
            raise EvidenceError("EVIDENCE_AUDIT_UNAVAILABLE") from None

    def schedule_retry(
        self,
        evidence: EvidenceObject,
        *,
        operation: str,
        error_code: str,
        changed_at: datetime,
    ) -> None:
        columns = {
            "upload": (
                evidence_objects.c.upload_attempt_count,
                "next_upload_attempt_at",
                "last_upload_error_code",
                EvidenceState.PENDING_UPLOAD.value,
            ),
            "reconciliation": (
                evidence_objects.c.reconciliation_attempt_count,
                "next_reconciliation_at",
                "last_reconciliation_error_code",
                None,
            ),
            "delete": (
                evidence_objects.c.delete_attempt_count,
                "next_delete_attempt_at",
                "last_delete_error_code",
                EvidenceState.DELETE_PENDING.value,
            ),
        }
        try:
            attempt_column, next_name, error_name, required_state = columns[operation]
        except KeyError:
            raise EvidenceError("EVIDENCE_RETRY_INVALID") from None
        where = [
            evidence_objects.c.evidence_id == evidence.evidence_id,
            evidence_objects.c.tenant_id == evidence.tenant_id,
            evidence_objects.c.school_id == evidence.school_id,
            attempt_column < 5,
        ]
        if required_state is not None:
            where.append(evidence_objects.c.state == required_state)
        values: dict[str, object] = {
            next_name: changed_at + timedelta(seconds=30),
            error_name: error_code,
            "updated_at": changed_at,
        }
        values[attempt_column.name] = attempt_column + 1
        try:
            with self._engine.begin() as connection:
                updated = connection.execute(
                    sa.update(evidence_objects).where(*where).values(**values)
                )
                if updated.rowcount != 1:
                    raise EvidenceError("EVIDENCE_RETRY_EXHAUSTED")
        except EvidenceError:
            raise
        except SQLAlchemyError:
            raise EvidenceError("EVIDENCE_DATABASE_UNAVAILABLE") from None
