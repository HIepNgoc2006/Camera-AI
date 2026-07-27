"""Tenant-scoped PostgreSQL repository with atomic consent audit intents."""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    AuthorityType,
    Consent,
    ConsentAuditIntent,
    ConsentChangeOutcome,
    ConsentEvent,
    ConsentEventType,
    ConsentStatus,
    ConsentTransitionRequest,
    Purpose,
    PurposeStatus,
    SubjectType,
    TrustedConsentContext,
    transition_consent,
)
from consent_service.domain.policies import AUDIT_ACTIONS
from consent_service.domain.processing import ProcessingLookup
from consent_service.infrastructure.tables import (
    consent_audit_outbox,
    consent_events,
    consents,
    purposes,
)

_PROCESSING_LOOKUP_CAP = 8


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else _uuid(value)


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ConsentError("CONSENT_UNAVAILABLE")
    return value


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _purpose(row: RowMapping, prefix: str = "") -> Purpose:
    return Purpose(
        purpose_id=_uuid(row[f"{prefix}purpose_id"]),
        school_id=_optional_uuid(row[f"{prefix}school_id"]),
        code=str(row[f"{prefix}code"]),
        description=str(row[f"{prefix}description"]),
        data_categories=tuple(cast(list[str], row[f"{prefix}data_categories"])),
        requires_biometric_consent=bool(row[f"{prefix}requires_biometric_consent"]),
        status=PurposeStatus(str(row[f"{prefix}status"])),
        version=int(cast(int, row[f"{prefix}version"])),
        valid_from=_datetime(row[f"{prefix}valid_from"]),
        valid_to=_optional_datetime(row[f"{prefix}valid_to"]),
        created_at=_datetime(row[f"{prefix}created_at"]),
    )


def _consent(row: RowMapping, prefix: str = "") -> Consent:
    return Consent(
        consent_id=_uuid(row[f"{prefix}consent_id"]),
        school_id=_uuid(row[f"{prefix}school_id"]),
        subject_type=SubjectType(str(row[f"{prefix}subject_type"])),
        subject_id=_uuid(row[f"{prefix}subject_id"]),
        purpose_id=_uuid(row[f"{prefix}purpose_id"]),
        authority_type=AuthorityType(str(row[f"{prefix}authority_type"])),
        authority_ref=_uuid(row[f"{prefix}authority_ref"]),
        status=ConsentStatus(str(row[f"{prefix}status"])),
        scope_codes=tuple(cast(list[str], row[f"{prefix}scope_codes"])),
        valid_from=_optional_datetime(row[f"{prefix}valid_from"]),
        valid_to=_optional_datetime(row[f"{prefix}valid_to"]),
        withdrawn_at=_optional_datetime(row[f"{prefix}withdrawn_at"]),
        restricted_at=_optional_datetime(row[f"{prefix}restricted_at"]),
        policy_version=str(row[f"{prefix}policy_version"]),
        created_at=_datetime(row[f"{prefix}created_at"]),
        updated_at=_datetime(row[f"{prefix}updated_at"]),
        row_version=int(cast(int, row[f"{prefix}row_version"])),
    )


def _event(row: RowMapping, prefix: str = "") -> ConsentEvent:
    fingerprint = row[f"{prefix}request_fingerprint"]
    return ConsentEvent(
        consent_event_id=_uuid(row[f"{prefix}consent_event_id"]),
        school_id=_uuid(row[f"{prefix}school_id"]),
        consent_id=_uuid(row[f"{prefix}consent_id"]),
        event_type=ConsentEventType(str(row[f"{prefix}event_type"])),
        actor_id=_uuid(row[f"{prefix}actor_id"]),
        reason_code=(
            None if row[f"{prefix}reason_code"] is None else str(row[f"{prefix}reason_code"])
        ),
        request_id=str(row[f"{prefix}request_id"]),
        evidence_ref=(
            None if row[f"{prefix}evidence_ref"] is None else str(row[f"{prefix}evidence_ref"])
        ),
        idempotency_key=str(row[f"{prefix}idempotency_key"]),
        request_fingerprint=bytes(fingerprint),
        resulting_version=int(cast(int, row[f"{prefix}resulting_version"])),
        occurred_at=_datetime(row[f"{prefix}occurred_at"]),
        recorded_at=_datetime(row[f"{prefix}recorded_at"]),
    )


def _intent(row: RowMapping, prefix: str = "") -> ConsentAuditIntent:
    return ConsentAuditIntent(
        audit_intent_id=_uuid(row[f"{prefix}audit_intent_id"]),
        consent_event_id=_uuid(row[f"{prefix}consent_event_id"]),
        source_event_id=_uuid(row[f"{prefix}source_event_id"]),
        school_id=_uuid(row[f"{prefix}school_id"]),
        actor_id=_uuid(row[f"{prefix}actor_id"]),
        action=str(row[f"{prefix}action"]),
        purpose_code=str(row[f"{prefix}purpose_code"]),
        resource_id=_uuid(row[f"{prefix}resource_id"]),
        request_id=str(row[f"{prefix}request_id"]),
        result=str(row[f"{prefix}result"]),
        reason_code=(
            None if row[f"{prefix}reason_code"] is None else str(row[f"{prefix}reason_code"])
        ),
        state_before=(
            None if row[f"{prefix}state_before"] is None else str(row[f"{prefix}state_before"])
        ),
        state_after=str(row[f"{prefix}state_after"]),
        policy_version=str(row[f"{prefix}policy_version"]),
        created_at=_datetime(row[f"{prefix}created_at"]),
    )


def _purpose_values(item: Purpose) -> dict[str, object]:
    return {
        "purpose_id": item.purpose_id,
        "school_id": item.school_id,
        "code": item.code,
        "description": item.description,
        "data_categories": list(item.data_categories),
        "requires_biometric_consent": item.requires_biometric_consent,
        "status": item.status.value,
        "version": item.version,
        "valid_from": item.valid_from,
        "valid_to": item.valid_to,
        "created_at": item.created_at,
    }


def _consent_values(item: Consent) -> dict[str, object]:
    return {
        "consent_id": item.consent_id,
        "school_id": item.school_id,
        "subject_type": item.subject_type.value,
        "subject_id": item.subject_id,
        "purpose_id": item.purpose_id,
        "authority_type": item.authority_type.value,
        "authority_ref": item.authority_ref,
        "status": item.status.value,
        "scope_codes": list(item.scope_codes),
        "valid_from": item.valid_from,
        "valid_to": item.valid_to,
        "withdrawn_at": item.withdrawn_at,
        "restricted_at": item.restricted_at,
        "policy_version": item.policy_version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "row_version": item.row_version,
    }


def _event_values(item: ConsentEvent) -> dict[str, object]:
    return {
        "consent_event_id": item.consent_event_id,
        "school_id": item.school_id,
        "consent_id": item.consent_id,
        "event_type": item.event_type.value,
        "actor_id": item.actor_id,
        "reason_code": item.reason_code,
        "request_id": item.request_id,
        "evidence_ref": item.evidence_ref,
        "idempotency_key": item.idempotency_key,
        "request_fingerprint": item.request_fingerprint,
        "resulting_version": item.resulting_version,
        "occurred_at": item.occurred_at,
        "recorded_at": item.recorded_at,
    }


def _intent_values(item: ConsentAuditIntent) -> dict[str, object]:
    return {
        "audit_intent_id": item.audit_intent_id,
        "consent_event_id": item.consent_event_id,
        "event_schema_version": 1,
        "source_service": "consent-service",
        "source_event_id": item.source_event_id,
        "school_id": item.school_id,
        "actor_id": item.actor_id,
        "action": item.action,
        "purpose_code": item.purpose_code,
        "resource_type": "consent",
        "resource_id": item.resource_id,
        "request_id": item.request_id,
        "result": item.result,
        "reason_code": item.reason_code,
        "state_before": item.state_before,
        "state_after": item.state_after,
        "policy_version": item.policy_version,
        "delivery_status": "pending",
        "published_at": None,
        "attempt_count": 0,
        "created_at": item.created_at,
    }


def _existing_outcome(
    connection: Connection,
    school_id: UUID,
    idempotency_key: str,
    fingerprint: bytes,
) -> ConsentChangeOutcome | None:
    event_row = (
        connection.execute(
            sa.select(consent_events).where(
                consent_events.c.school_id == school_id,
                consent_events.c.idempotency_key == idempotency_key,
            )
        )
        .mappings()
        .one_or_none()
    )
    if event_row is None:
        return None
    event = _event(event_row)
    if not hmac.compare_digest(event.request_fingerprint, fingerprint):
        raise ConsentError("CONSENT_DUPLICATE_CONFLICT")
    consent_row = (
        connection.execute(
            sa.select(consents).where(
                consents.c.school_id == school_id,
                consents.c.consent_id == event.consent_id,
            )
        )
        .mappings()
        .one()
    )
    intent_row = (
        connection.execute(
            sa.select(consent_audit_outbox).where(
                consent_audit_outbox.c.consent_event_id == event.consent_event_id
            )
        )
        .mappings()
        .one()
    )
    return ConsentChangeOutcome(_consent(consent_row), event, _intent(intent_row), duplicate=True)


class SqlAlchemyConsentRepository:
    """Own only the privacy schema and never resolve logical references cross-schema."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def register_purpose(self, purpose: Purpose) -> Purpose:
        try:
            with self._engine.begin() as connection:
                connection.execute(sa.insert(purposes).values(**_purpose_values(purpose)))
            return purpose
        except IntegrityError:
            raise ConsentError("CONSENT_ALREADY_EXISTS") from None
        except SQLAlchemyError:
            raise ConsentError("CONSENT_UNAVAILABLE") from None

    def get_purpose(self, purpose_id: UUID, school_id: UUID) -> Purpose | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(purposes).where(
                            purposes.c.purpose_id == purpose_id,
                            sa.or_(
                                purposes.c.school_id == school_id, purposes.c.school_id.is_(None)
                            ),
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return None if row is None else _purpose(row)
        except ConsentError:
            raise
        except SQLAlchemyError:
            raise ConsentError("CONSENT_UNAVAILABLE") from None

    def create_consent(
        self,
        consent: Consent,
        event: ConsentEvent,
        audit_intent: ConsentAuditIntent,
    ) -> ConsentChangeOutcome:
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                    {"identity": f"{consent.school_id}:{event.idempotency_key}"},
                )
                existing = _existing_outcome(
                    connection,
                    consent.school_id,
                    event.idempotency_key,
                    event.request_fingerprint,
                )
                if existing is not None:
                    return existing
                connection.execute(
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:subject, 1))"),
                    {
                        "subject": (
                            f"{consent.school_id}:{consent.subject_type.value}:"
                            f"{consent.subject_id}:{consent.purpose_id}"
                        )
                    },
                )
                duplicate = connection.scalar(
                    sa.select(consents.c.consent_id).where(
                        consents.c.school_id == consent.school_id,
                        consents.c.subject_type == consent.subject_type.value,
                        consents.c.subject_id == consent.subject_id,
                        consents.c.purpose_id == consent.purpose_id,
                    )
                )
                if duplicate is not None:
                    raise ConsentError("CONSENT_ALREADY_EXISTS")
                connection.execute(sa.insert(consents).values(**_consent_values(consent)))
                connection.execute(sa.insert(consent_events).values(**_event_values(event)))
                connection.execute(
                    sa.insert(consent_audit_outbox).values(**_intent_values(audit_intent))
                )
                return ConsentChangeOutcome(consent, event, audit_intent, duplicate=False)
        except ConsentError:
            raise
        except IntegrityError:
            raise ConsentError("CONSENT_ALREADY_EXISTS") from None
        except SQLAlchemyError:
            raise ConsentError("CONSENT_UNAVAILABLE") from None

    def transition_consent(
        self,
        request: ConsentTransitionRequest,
        context: TrustedConsentContext,
    ) -> ConsentChangeOutcome:
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                    {"identity": f"{context.school_id}:{request.idempotency_key}"},
                )
                existing = _existing_outcome(
                    connection,
                    context.school_id,
                    request.idempotency_key,
                    request.request_fingerprint,
                )
                if existing is not None:
                    return existing
                row = (
                    connection.execute(
                        sa.select(consents)
                        .where(
                            consents.c.school_id == context.school_id,
                            consents.c.consent_id == request.consent_id,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise ConsentError("CONSENT_NOT_FOUND")
                current = _consent(row)
                if (
                    current.subject_type is not context.subject_type
                    or current.subject_id != context.subject_id
                    or current.authority_type is not context.authority_type
                    or current.authority_ref != context.authority_ref
                    or not context.authority_verified
                ):
                    raise ConsentError("CONSENT_AUTHORITY_DENIED")
                if current.row_version != request.expected_version:
                    raise ConsentError("CONSENT_VERSION_CONFLICT")
                purpose_row = (
                    connection.execute(
                        sa.select(purposes).where(
                            purposes.c.purpose_id == current.purpose_id,
                            sa.or_(
                                purposes.c.school_id == context.school_id,
                                purposes.c.school_id.is_(None),
                            ),
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if purpose_row is None:
                    raise ConsentError("CONSENT_PURPOSE_INACTIVE")
                purpose = _purpose(purpose_row)
                updated = transition_consent(
                    current,
                    request.target_status,
                    changed_at=request.changed_at,
                )
                event_type = ConsentEventType(request.target_status.value)
                event = ConsentEvent(
                    consent_event_id=request.consent_event_id,
                    school_id=context.school_id,
                    consent_id=current.consent_id,
                    event_type=event_type,
                    actor_id=context.actor_id,
                    reason_code=request.reason_code,
                    request_id=request.request_id,
                    evidence_ref=request.evidence_ref,
                    idempotency_key=request.idempotency_key,
                    request_fingerprint=request.request_fingerprint,
                    resulting_version=updated.row_version,
                    occurred_at=request.changed_at,
                    recorded_at=request.changed_at,
                )
                intent = ConsentAuditIntent(
                    audit_intent_id=request.audit_intent_id,
                    consent_event_id=request.consent_event_id,
                    source_event_id=request.consent_event_id,
                    school_id=context.school_id,
                    actor_id=context.actor_id,
                    action=AUDIT_ACTIONS[event_type],
                    purpose_code=purpose.code,
                    resource_id=current.consent_id,
                    request_id=request.request_id,
                    result=("denied" if event_type is ConsentEventType.DENIED else "success"),
                    reason_code=request.reason_code,
                    state_before=current.status.value,
                    state_after=updated.status.value,
                    policy_version=current.policy_version,
                    created_at=request.changed_at,
                )
                result = connection.execute(
                    sa.update(consents)
                    .where(
                        consents.c.consent_id == current.consent_id,
                        consents.c.school_id == context.school_id,
                        consents.c.row_version == request.expected_version,
                    )
                    .values(**_consent_values(updated))
                )
                if result.rowcount != 1:
                    raise ConsentError("CONSENT_VERSION_CONFLICT")
                connection.execute(sa.insert(consent_events).values(**_event_values(event)))
                connection.execute(sa.insert(consent_audit_outbox).values(**_intent_values(intent)))
                return ConsentChangeOutcome(updated, event, intent, duplicate=False)
        except ConsentError:
            raise
        except IntegrityError:
            raise ConsentError("CONSENT_DUPLICATE_CONFLICT") from None
        except SQLAlchemyError:
            raise ConsentError("CONSENT_UNAVAILABLE") from None

    def find_for_processing(
        self,
        *,
        school_id: UUID,
        subject_type: SubjectType,
        subject_id: UUID | None,
        purpose_code: str,
    ) -> ProcessingLookup:
        """Bounded tenant-filtered snapshot for one Issue #139 gate evaluation.

        The cap only bounds transport; the pure decision layer treats more than
        one active purpose or matching consent as ambiguity and denies.
        """

        try:
            with self._engine.connect() as connection:
                purpose_rows = (
                    connection.execute(
                        sa.select(purposes)
                        .where(
                            purposes.c.code == purpose_code,
                            sa.or_(
                                purposes.c.school_id == school_id,
                                purposes.c.school_id.is_(None),
                            ),
                        )
                        .order_by(purposes.c.version, purposes.c.purpose_id)
                        .limit(_PROCESSING_LOOKUP_CAP)
                    )
                    .mappings()
                    .all()
                )
                consent_rows = []
                if subject_id is not None and purpose_rows:
                    consent_rows = list(
                        connection.execute(
                            sa.select(consents)
                            .where(
                                consents.c.school_id == school_id,
                                consents.c.subject_type == subject_type.value,
                                consents.c.subject_id == subject_id,
                                consents.c.purpose_id.in_(
                                    [row["purpose_id"] for row in purpose_rows]
                                ),
                            )
                            .order_by(consents.c.consent_id)
                            .limit(_PROCESSING_LOOKUP_CAP)
                        )
                        .mappings()
                        .all()
                    )
            return ProcessingLookup(
                purposes=tuple(_purpose(row) for row in purpose_rows),
                consents=tuple(_consent(row) for row in consent_rows),
            )
        except ConsentError:
            raise
        except SQLAlchemyError:
            raise ConsentError("CONSENT_UNAVAILABLE") from None

    def get_for_evaluation(
        self,
        consent_id: UUID,
        school_id: UUID,
    ) -> tuple[Consent | None, Purpose | None]:
        try:
            consent_columns = [column.label(f"consent_{column.name}") for column in consents.c]
            purpose_columns = [column.label(f"purpose_{column.name}") for column in purposes.c]
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(*consent_columns, *purpose_columns)
                        .select_from(
                            consents.join(purposes, consents.c.purpose_id == purposes.c.purpose_id)
                        )
                        .where(
                            consents.c.consent_id == consent_id,
                            consents.c.school_id == school_id,
                            sa.or_(
                                purposes.c.school_id == school_id, purposes.c.school_id.is_(None)
                            ),
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            if row is None:
                return None, None
            return _consent(row, "consent_"), _purpose(row, "purpose_")
        except ConsentError:
            raise
        except SQLAlchemyError:
            raise ConsentError("CONSENT_UNAVAILABLE") from None
