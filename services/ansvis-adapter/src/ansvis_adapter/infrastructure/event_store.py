"""PostgreSQL durable receipt, normalized event, quarantine and outbox repository."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import sqlalchemy as sa
from camera_ai_audit import AuditIntent, IntentResult
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    ConsentGate,
    DurableReceipt,
    DurableReceiptPort,
    EventScopeResolver,
    MetricsSink,
    OperationalStatusRepository,
    OutboxRepository,
    ReceiptOutcome,
)
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.domain.consent import (
    CONSENT_BLOCKED,
    CONSENT_GATE_POLICY_VERSION,
    CONSENT_UNAVAILABLE,
    NOT_REQUIRED_DECISION,
    ConsentGateDecision,
    ConsentGateRequest,
    ConsentGateStatus,
    consent_purpose_for,
)
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import IdempotencyDescriptor
from ansvis_adapter.domain.ingestion import (
    EventOperationalSnapshot,
    PendingOutboxMessage,
    ReplayAuthorization,
    ResolvedEventScope,
)
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.audit_outbox import enqueue_audit_intent
from ansvis_adapter.infrastructure.tables import (
    event_detections,
    ingestion_receipts,
    normalized_events,
    outbox_messages,
    processing_attempts,
)

CONTRACT_VERSION = "ansvis_http_trigger_v1"
OUTBOX_CONTRACT_VERSION = "normalized_outbox_v1"
CONSUMER_PUBLISHER = "outbox-publisher"
CONSUMER_CONFLICT = "ingestion-conflict"
CONSUMER_REPLAY = "outbox-replay"
CONSUMER_CONSENT_GUARD = "consent-guard"
AUDIT_SOURCE_SERVICE = "event-ingestion-service"
CONSENT_AUDIT_ACTION = "EVENT_CONSENT_DENIED"
CONSENT_GATE_METRIC = "event_consent_gate_total"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
    return value.astimezone(UTC)


def _checksum(fingerprint: str) -> bytes:
    prefix, separator, digest = fingerprint.partition(":")
    if prefix != "sha256" or separator != ":" or len(digest) != 64:
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
    try:
        return bytes.fromhex(digest)
    except ValueError:
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None


def _fingerprint(checksum: object) -> str:
    if isinstance(checksum, memoryview):
        checksum = checksum.tobytes()
    elif isinstance(checksum, bytearray):
        checksum = bytes(checksum)
    if not isinstance(checksum, bytes) or len(checksum) != 32:
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
    return f"sha256:{checksum.hex()}"


def _topic(event: NormalizedAnsvisEvent) -> str:
    suffix = event.event_type.value.replace(".", "_")
    return f"camera_ai.events.{suffix}.v1"


def _versions(event: NormalizedAnsvisEvent) -> tuple[str, str]:
    model = event.attributes.model_version or "not_applicable_v1"
    config = event.attributes.config_version or "not_supplied_v1"
    return model, config


def _safe_metadata(event: NormalizedAnsvisEvent) -> dict[str, object]:
    attributes = event.attributes
    result: dict[str, object] = {"schema_version": "event_metadata_v1"}
    if attributes.status is not None:
        result["status"] = attributes.status.value
    if attributes.rule_code is not None:
        result["rule_code"] = attributes.rule_code
    if attributes.detection_count is not None:
        result["detection_count"] = attributes.detection_count
    return result


def _detection_attributes(event: NormalizedAnsvisEvent) -> dict[str, object]:
    attributes = event.attributes
    result: dict[str, object] = {"schema_version": "detection_attributes_v1"}
    if attributes.track_id is not None:
        result["track_id"] = attributes.track_id
    if attributes.detection_key is not None:
        result["detection_key"] = attributes.detection_key
    if attributes.rule_code is not None:
        result["rule_code"] = attributes.rule_code
    if attributes.detection_count is not None:
        result["detection_count"] = attributes.detection_count
    return result


def _outbox_payload(
    event: NormalizedAnsvisEvent,
    *,
    event_id: UUID,
    school_id: UUID,
    source_id: UUID,
    camera_id: UUID,
    task_id: UUID,
    decision: ConsentGateDecision,
) -> dict[str, object]:
    model_version, config_version = _versions(event)
    payload: dict[str, object] = {
        "schema_version": OUTBOX_CONTRACT_VERSION,
        "normalized_event_id": str(event_id),
        "school_id": str(school_id),
        "source_id": str(source_id),
        "camera_id": str(camera_id),
        "task_id": str(task_id),
        "event_type": event.event_type.value,
        "event_time": event.occurred_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "correlation_id": event.correlation_id,
        "model_version": model_version,
        "config_version": config_version,
        "consent_gate_status": decision.status.value,
        "consent_policy_version": decision.policy_version,
    }
    if event.attributes.confidence is not None:
        payload["confidence"] = event.attributes.confidence
    payload["metadata"] = _safe_metadata(event)
    return payload


def _system_utc_now() -> datetime:
    return datetime.now(UTC)


def _next_attempt_number(connection: Connection, event_id: UUID, consumer: str) -> int:
    current = connection.scalar(
        sa.select(sa.func.max(processing_attempts.c.attempt_number)).where(
            processing_attempts.c.normalized_event_id == event_id,
            processing_attempts.c.consumer == consumer,
        )
    )
    return 1 if current is None else int(current) + 1


class PostgresEventIngestionRepository(
    DurableReceiptPort,
    OutboxRepository,
    OperationalStatusRepository,
):
    """Own the Event Ingestion transaction without reading another service schema."""

    def __init__(
        self,
        engine: Engine,
        *,
        scopes: EventScopeResolver,
        consent_gate: ConsentGate,
        retention_days: int,
        claim_seconds: int = 30,
        now: Callable[[], datetime] = _system_utc_now,
        metrics: MetricsSink | None = None,
    ) -> None:
        if not 1 <= retention_days <= 3_650:
            raise ValueError("retention_days must come from an approved bounded policy")
        if claim_seconds != 30:
            raise ValueError("claim lease must match normalized_outbox_v1")
        self._engine = engine
        self._scopes = scopes
        self._consent_gate = consent_gate
        self._retention_days = retention_days
        self._claim_seconds = claim_seconds
        self._now = now
        self._metrics = metrics or NullMetricsSink()

    def record(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        idempotency: IdempotencyDescriptor,
    ) -> DurableReceipt:
        try:
            scope = self._scopes.resolve(event, source)
        except AnsvisAdapterError:
            raise
        except Exception:
            raise AnsvisAdapterError("EVENT_SOURCE_MAPPING_DENIED") from None

        purpose_code = consent_purpose_for(event.event_type)
        decision = self._evaluate_consent(event, source, scope, purpose_code)
        received_at = _utc(self._now())
        retention_until = received_at + timedelta(days=self._retention_days)
        receipt_uuid = uuid4()
        event_id = uuid4()
        checksum = _checksum(idempotency.canonical_fingerprint)
        conflict = False
        deferred = decision is None
        result: DurableReceipt | None = None
        try:
            with self._engine.begin() as connection:
                inserted = connection.execute(
                    pg_insert(ingestion_receipts)
                    .values(
                        ingestion_receipt_id=receipt_uuid,
                        school_id=scope.school_id,
                        source_id=scope.source_id,
                        idempotency_key=idempotency.idempotency_key,
                        payload_schema_version=CONTRACT_VERSION,
                        payload_checksum=checksum,
                        request_id=event.correlation_id,
                        received_at=received_at,
                        result="deferred" if deferred else "accepted",
                        error_code=CONSENT_UNAVAILABLE if deferred else None,
                        occurred_at=event.occurred_at,
                        recorded_at=received_at,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            ingestion_receipts.c.source_id,
                            ingestion_receipts.c.idempotency_key,
                        ]
                    )
                    .returning(ingestion_receipts.c.ingestion_receipt_id)
                ).scalar_one_or_none()
                if inserted is None:
                    result, conflict = self._continue_existing_receipt(
                        connection,
                        event=event,
                        scope=scope,
                        idempotency=idempotency,
                        decision=decision,
                        purpose_code=purpose_code,
                        event_id=event_id,
                        received_at=received_at,
                        retention_until=retention_until,
                    )
                elif deferred:
                    self._enqueue_consent_audit(
                        connection,
                        receipt_uuid=receipt_uuid,
                        event_id=None,
                        scope=scope,
                        purpose_code=purpose_code,
                        reason_code=CONSENT_UNAVAILABLE,
                        policy_version=CONSENT_GATE_POLICY_VERSION,
                        occurred_at=received_at,
                    )
                else:
                    result = self._materialize_event(
                        connection,
                        event=event,
                        scope=scope,
                        receipt_uuid=receipt_uuid,
                        event_id=event_id,
                        decision=cast(ConsentGateDecision, decision),
                        purpose_code=purpose_code,
                        idempotency=idempotency,
                        recorded_at=received_at,
                        retention_until=retention_until,
                    )
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
        if conflict:
            raise AnsvisAdapterError("EVENT_IDEMPOTENCY_CONFLICT")
        if result is None:
            # The durable deferred receipt is committed; the source must retry
            # idempotently until the consent gate can produce a real decision.
            self._consent_metric("unavailable")
            raise AnsvisAdapterError(CONSENT_UNAVAILABLE)
        return result

    def _evaluate_consent(
        self,
        event: NormalizedAnsvisEvent,
        source: AuthenticatedSource,
        scope: ResolvedEventScope,
        purpose_code: str | None,
    ) -> ConsentGateDecision | None:
        """Return the strict decision, or None when the gate is unavailable."""

        if purpose_code is None:
            return NOT_REQUIRED_DECISION
        try:
            decision = self._consent_gate.evaluate(
                ConsentGateRequest(
                    school_id=scope.school_id,
                    tenant_ref=source.tenant_ref,
                    school_ref=source.school_ref,
                    subject_ref=event.attributes.subject_external_id,
                    purpose_code=purpose_code,
                    policy_version=CONSENT_GATE_POLICY_VERSION,
                )
            )
        except Exception:
            return None
        if not isinstance(decision, ConsentGateDecision):
            return None
        return decision

    def _continue_existing_receipt(
        self,
        connection: Connection,
        *,
        event: NormalizedAnsvisEvent,
        scope: ResolvedEventScope,
        idempotency: IdempotencyDescriptor,
        decision: ConsentGateDecision | None,
        purpose_code: str | None,
        event_id: UUID,
        received_at: datetime,
        retention_until: datetime,
    ) -> tuple[DurableReceipt | None, bool]:
        """Resolve a receipt conflict: duplicate, fingerprint conflict, or a
        deferred receipt resuming with a fresh consent decision."""

        receipt_row = (
            connection.execute(
                sa.select(
                    ingestion_receipts.c.ingestion_receipt_id,
                    ingestion_receipts.c.payload_checksum,
                    ingestion_receipts.c.result,
                )
                .where(
                    ingestion_receipts.c.source_id == scope.source_id,
                    ingestion_receipts.c.idempotency_key == idempotency.idempotency_key,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        existing_receipt_id = cast(UUID, receipt_row["ingestion_receipt_id"])
        existing_event_id = cast(
            UUID | None,
            connection.scalar(
                sa.select(normalized_events.c.normalized_event_id).where(
                    normalized_events.c.ingestion_receipt_id == existing_receipt_id
                )
            ),
        )
        stored_fingerprint = _fingerprint(receipt_row["payload_checksum"])
        if stored_fingerprint != idempotency.canonical_fingerprint:
            if existing_event_id is not None:
                connection.execute(
                    sa.insert(processing_attempts).values(
                        processing_attempt_id=uuid4(),
                        normalized_event_id=existing_event_id,
                        consumer=CONSUMER_CONFLICT,
                        attempt_number=_next_attempt_number(
                            connection, existing_event_id, CONSUMER_CONFLICT
                        ),
                        result="dead_lettered",
                        error_code="EVENT_IDEMPOTENCY_CONFLICT",
                        next_retry_at=None,
                        duration_ms=None,
                        actor_id=None,
                        reason_code=None,
                        occurred_at=received_at,
                        recorded_at=received_at,
                    )
                )
            return None, True
        if existing_event_id is not None:
            return (
                DurableReceipt(
                    receipt_id=f"receipt_{existing_receipt_id.hex}",
                    outcome=ReceiptOutcome.DUPLICATE,
                    commit_confirmed=True,
                    idempotency_key=idempotency.idempotency_key,
                    canonical_fingerprint=stored_fingerprint,
                ),
                False,
            )
        if str(receipt_row["result"]) != "deferred":
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
        if decision is None:
            return None, False
        return (
            self._materialize_event(
                connection,
                event=event,
                scope=scope,
                receipt_uuid=existing_receipt_id,
                event_id=event_id,
                decision=decision,
                purpose_code=purpose_code,
                idempotency=idempotency,
                recorded_at=received_at,
                retention_until=retention_until,
            ),
            False,
        )

    def _materialize_event(
        self,
        connection: Connection,
        *,
        event: NormalizedAnsvisEvent,
        scope: ResolvedEventScope,
        receipt_uuid: UUID,
        event_id: UUID,
        decision: ConsentGateDecision,
        purpose_code: str | None,
        idempotency: IdempotencyDescriptor,
        recorded_at: datetime,
        retention_until: datetime,
    ) -> DurableReceipt:
        blocked = decision.status is ConsentGateStatus.BLOCKED
        model_version, config_version = _versions(event)
        connection.execute(
            sa.insert(normalized_events).values(
                normalized_event_id=event_id,
                ingestion_receipt_id=receipt_uuid,
                school_id=scope.school_id,
                source_id=scope.source_id,
                camera_id=scope.camera_id,
                task_id=scope.task_id,
                event_type=event.event_type.value,
                event_time=event.occurred_at,
                source_timezone="UTC",
                # A blocked event keeps only the minimized rejected link: scope,
                # type, time and correlation. No confidence, no detection row,
                # no outbox fan-out.
                confidence=None if blocked else event.attributes.confidence,
                zone_ref=scope.zone_id,
                model_version=model_version,
                config_version=config_version,
                correlation_id=event.correlation_id,
                sanitized_metadata=(
                    {"schema_version": "event_metadata_v1"} if blocked else _safe_metadata(event)
                ),
                consent_gate_status=decision.status.value,
                consent_policy_version=decision.policy_version,
                retention_until=retention_until,
                occurred_at=event.occurred_at,
                recorded_at=recorded_at,
            )
        )
        if blocked:
            self._enqueue_consent_audit(
                connection,
                receipt_uuid=receipt_uuid,
                event_id=event_id,
                scope=scope,
                purpose_code=purpose_code,
                reason_code=decision.reason_code,
                policy_version=decision.policy_version,
                occurred_at=recorded_at,
            )
        else:
            detection_attributes = _detection_attributes(event)
            if len(detection_attributes) > 1:
                connection.execute(
                    sa.insert(event_detections).values(
                        event_detection_id=uuid4(),
                        normalized_event_id=event_id,
                        detection_index=0,
                        subject_type=None,
                        subject_ref=None,
                        subject_match_confidence=None,
                        emotion_label=None,
                        emotion_confidence=None,
                        attributes=detection_attributes,
                        retention_until=retention_until,
                        occurred_at=event.occurred_at,
                        recorded_at=recorded_at,
                    )
                )
            connection.execute(
                sa.insert(outbox_messages).values(
                    outbox_message_id=uuid4(),
                    normalized_event_id=event_id,
                    topic=_topic(event),
                    contract_version=OUTBOX_CONTRACT_VERSION,
                    payload=_outbox_payload(
                        event,
                        event_id=event_id,
                        school_id=scope.school_id,
                        source_id=scope.source_id,
                        camera_id=scope.camera_id,
                        task_id=scope.task_id,
                        decision=decision,
                    ),
                    publish_status="pending",
                    published_at=None,
                    attempt_count=0,
                    next_attempt_at=recorded_at,
                    claim_token=None,
                    claim_expires_at=None,
                    occurred_at=event.occurred_at,
                    recorded_at=recorded_at,
                )
            )
        self._consent_metric(decision.status.value)
        return DurableReceipt(
            receipt_id=f"receipt_{receipt_uuid.hex}",
            outcome=ReceiptOutcome.ACCEPTED,
            commit_confirmed=True,
            idempotency_key=idempotency.idempotency_key,
            canonical_fingerprint=idempotency.canonical_fingerprint,
        )

    def _enqueue_consent_audit(
        self,
        connection: Connection,
        *,
        receipt_uuid: UUID,
        event_id: UUID | None,
        scope: ResolvedEventScope,
        purpose_code: str | None,
        reason_code: str,
        policy_version: str,
        occurred_at: datetime,
    ) -> None:
        """Enqueue exactly one denial evidence intent inside the same transaction.

        The intent identity derives from the immutable receipt identity, so a
        retried ingestion can never produce duplicate evidence downstream.
        """

        marker = "consent-blocked" if event_id is not None else "consent-deferred"
        references: tuple[tuple[str, UUID], ...] = (("receipt_id", receipt_uuid),)
        if event_id is not None:
            references = (("event_id", event_id),) + references
        enqueue_audit_intent(
            connection,
            AuditIntent(
                source_service=AUDIT_SOURCE_SERVICE,
                source_event_id=uuid5(NAMESPACE_URL, f"camera-ai:{marker}:{receipt_uuid}"),
                action=CONSENT_AUDIT_ACTION,
                resource_type="event" if event_id is not None else "ingestion_receipt",
                resource_id=event_id if event_id is not None else receipt_uuid,
                request_id=f"req_receipt_{receipt_uuid.hex}",
                result=IntentResult.DENIED,
                reason_code=reason_code,
                occurred_at=occurred_at,
                school_id=scope.school_id,
                purpose_code=purpose_code,
                reference_ids=references,
                policy_versions=(("consent_policy", policy_version),),
            ),
            now=occurred_at,
        )

    def _consent_metric(self, outcome: str) -> None:
        try:
            self._metrics.increment(CONSENT_GATE_METRIC, outcome=outcome)
        except Exception:
            return

    def claim_next(self, *, now: datetime) -> PendingOutboxMessage | None:
        messages = self.claim_batch(now=now, limit=1)
        return messages[0] if messages else None

    def claim_batch(self, *, now: datetime, limit: int) -> tuple[PendingOutboxMessage, ...]:
        if not 1 <= limit <= 50:
            raise ValueError("outbox claim batch size must stay within 1..50")
        current = _utc(now)
        token = uuid4()
        try:
            with self._engine.begin() as connection:
                rows = (
                    connection.execute(
                        sa.select(outbox_messages)
                        .where(
                            outbox_messages.c.publish_status == "pending",
                            outbox_messages.c.next_attempt_at <= current,
                            sa.or_(
                                outbox_messages.c.claim_token.is_(None),
                                outbox_messages.c.claim_expires_at <= current,
                            ),
                        )
                        .order_by(
                            outbox_messages.c.recorded_at, outbox_messages.c.outbox_message_id
                        )
                        .with_for_update(skip_locked=True)
                        .limit(limit)
                    )
                    .mappings()
                    .all()
                )
                if not rows:
                    return ()
                message_ids = [cast(UUID, row["outbox_message_id"]) for row in rows]
                claimed = connection.execute(
                    sa.update(outbox_messages)
                    .where(outbox_messages.c.outbox_message_id.in_(message_ids))
                    .values(
                        claim_token=token,
                        claim_expires_at=current + timedelta(seconds=self._claim_seconds),
                    )
                )
                if claimed.rowcount != len(message_ids):
                    raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
                return tuple(
                    PendingOutboxMessage(
                        outbox_message_id=cast(UUID, row["outbox_message_id"]),
                        normalized_event_id=cast(UUID, row["normalized_event_id"]),
                        claim_token=token,
                        topic=str(row["topic"]),
                        contract_version=str(row["contract_version"]),
                        payload=cast(Mapping[str, object], row["payload"]),
                        attempt_count=int(row["attempt_count"]),
                        recorded_at=_utc(cast(datetime, row["recorded_at"])),
                    )
                    for row in rows
                )
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None

    def mark_published(
        self, message_id: UUID, claim_token: UUID, *, published_at: datetime
    ) -> None:
        self.mark_published_batch(((message_id, claim_token),), published_at=published_at)

    def mark_published_batch(
        self,
        confirmations: Sequence[tuple[UUID, UUID]],
        *,
        published_at: datetime,
    ) -> None:
        if not confirmations:
            return
        current = _utc(published_at)
        pairs = [
            sa.tuple_(sa.literal(message_id), sa.literal(claim_token))
            for message_id, claim_token in confirmations
        ]
        try:
            with self._engine.begin() as connection:
                result = connection.execute(
                    sa.update(outbox_messages)
                    .where(
                        sa.tuple_(
                            outbox_messages.c.outbox_message_id,
                            outbox_messages.c.claim_token,
                        ).in_(pairs),
                        outbox_messages.c.publish_status == "pending",
                    )
                    .values(
                        publish_status="published",
                        published_at=current,
                        claim_token=None,
                        claim_expires_at=None,
                    )
                )
                if result.rowcount != len(confirmations):
                    raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None

    def record_failure(
        self,
        message: PendingOutboxMessage,
        *,
        failed_at: datetime,
        next_retry_at: datetime | None,
        error_code: str,
    ) -> bool:
        current = _utc(failed_at)
        next_attempt = message.attempt_count + 1
        dead_lettered = next_retry_at is None
        if dead_lettered != (next_attempt >= 5) or error_code != "EVENT_OUTBOX_PUBLISH_FAILED":
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
        retry_at = current if next_retry_at is None else _utc(next_retry_at)
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        sa.select(outbox_messages.c.outbox_message_id)
                        .where(
                            outbox_messages.c.outbox_message_id == message.outbox_message_id,
                            outbox_messages.c.claim_token == message.claim_token,
                            outbox_messages.c.publish_status == "pending",
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
                connection.execute(
                    sa.update(outbox_messages)
                    .where(outbox_messages.c.outbox_message_id == message.outbox_message_id)
                    .values(
                        publish_status="failed" if dead_lettered else "pending",
                        attempt_count=next_attempt,
                        next_attempt_at=retry_at,
                        claim_token=None,
                        claim_expires_at=None,
                    )
                )
                connection.execute(
                    sa.insert(processing_attempts).values(
                        processing_attempt_id=uuid4(),
                        normalized_event_id=message.normalized_event_id,
                        consumer=CONSUMER_PUBLISHER,
                        attempt_number=next_attempt,
                        result="dead_lettered" if dead_lettered else "retryable",
                        error_code=error_code,
                        next_retry_at=None if dead_lettered else retry_at,
                        duration_ms=None,
                        actor_id=None,
                        reason_code=None,
                        occurred_at=current,
                        recorded_at=current,
                    )
                )
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
        return dead_lettered

    def replay_failed(
        self,
        message_id: UUID,
        *,
        actor_id: UUID,
        reason_code: str,
        authorized_at: datetime,
    ) -> None:
        try:
            authorization = ReplayAuthorization(
                actor_id=actor_id,
                reason_code=reason_code,
                approved=True,
                authorized_at=authorized_at,
            )
        except ValueError:
            raise AnsvisAdapterError("EVENT_REPLAY_DENIED") from None
        current = _utc(authorization.authorized_at)
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        sa.select(outbox_messages.c.normalized_event_id)
                        .where(
                            outbox_messages.c.outbox_message_id == message_id,
                            outbox_messages.c.publish_status == "failed",
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise AnsvisAdapterError("EVENT_REPLAY_DENIED")
                event_id = cast(UUID, row["normalized_event_id"])
                connection.execute(
                    sa.update(outbox_messages)
                    .where(outbox_messages.c.outbox_message_id == message_id)
                    .values(
                        publish_status="pending",
                        attempt_count=0,
                        next_attempt_at=current,
                        claim_token=None,
                        claim_expires_at=None,
                    )
                )
                connection.execute(
                    sa.insert(processing_attempts).values(
                        processing_attempt_id=uuid4(),
                        normalized_event_id=event_id,
                        consumer=CONSUMER_REPLAY,
                        attempt_number=_next_attempt_number(connection, event_id, CONSUMER_REPLAY),
                        result="retryable",
                        error_code="EVENT_REPLAY_APPROVED",
                        next_retry_at=current,
                        duration_ms=None,
                        actor_id=authorization.actor_id,
                        reason_code=authorization.reason_code,
                        occurred_at=current,
                        recorded_at=current,
                    )
                )
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None

    def refuse_consent_blocked(
        self,
        message: PendingOutboxMessage,
        *,
        refused_at: datetime,
    ) -> None:
        current = _utc(refused_at)
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        sa.select(outbox_messages.c.outbox_message_id)
                        .where(
                            outbox_messages.c.outbox_message_id == message.outbox_message_id,
                            outbox_messages.c.claim_token == message.claim_token,
                            outbox_messages.c.publish_status == "pending",
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
                connection.execute(
                    sa.update(outbox_messages)
                    .where(outbox_messages.c.outbox_message_id == message.outbox_message_id)
                    .values(
                        publish_status="refused",
                        next_attempt_at=current,
                        claim_token=None,
                        claim_expires_at=None,
                    )
                )
                connection.execute(
                    sa.insert(processing_attempts).values(
                        processing_attempt_id=uuid4(),
                        normalized_event_id=message.normalized_event_id,
                        consumer=CONSUMER_CONSENT_GUARD,
                        attempt_number=_next_attempt_number(
                            connection, message.normalized_event_id, CONSUMER_CONSENT_GUARD
                        ),
                        result="dead_lettered",
                        error_code=CONSENT_BLOCKED,
                        next_retry_at=None,
                        duration_ms=None,
                        actor_id=None,
                        reason_code=None,
                        occurred_at=current,
                        recorded_at=current,
                    )
                )
        except AnsvisAdapterError:
            raise
        except SQLAlchemyError:
            raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None

    def snapshot(self, *, now: datetime) -> EventOperationalSnapshot:
        current = _utc(now)
        delayed_before = current - timedelta(seconds=120)
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(
                            sa.select(sa.func.count())
                            .select_from(ingestion_receipts)
                            .where(ingestion_receipts.c.result == "accepted")
                            .scalar_subquery()
                            .label("accepted_receipts"),
                            sa.select(sa.func.count())
                            .select_from(outbox_messages)
                            .where(outbox_messages.c.publish_status == "pending")
                            .scalar_subquery()
                            .label("pending_messages"),
                            sa.select(sa.func.count())
                            .select_from(outbox_messages)
                            .where(outbox_messages.c.publish_status == "published")
                            .scalar_subquery()
                            .label("published_messages"),
                            sa.select(sa.func.count())
                            .select_from(outbox_messages)
                            .where(outbox_messages.c.publish_status == "failed")
                            .scalar_subquery()
                            .label("failed_messages"),
                            sa.select(sa.func.count())
                            .select_from(processing_attempts)
                            .where(
                                processing_attempts.c.consumer == CONSUMER_PUBLISHER,
                                processing_attempts.c.result == "retryable",
                            )
                            .scalar_subquery()
                            .label("retryable_attempts"),
                            sa.select(sa.func.count())
                            .select_from(processing_attempts)
                            .where(
                                processing_attempts.c.consumer == CONSUMER_CONFLICT,
                                processing_attempts.c.result == "dead_lettered",
                            )
                            .scalar_subquery()
                            .label("quarantined_conflicts"),
                            sa.select(sa.func.count())
                            .select_from(outbox_messages)
                            .where(
                                outbox_messages.c.publish_status == "pending",
                                outbox_messages.c.recorded_at < delayed_before,
                            )
                            .scalar_subquery()
                            .label("delayed_messages"),
                            sa.select(sa.func.min(outbox_messages.c.recorded_at))
                            .where(outbox_messages.c.publish_status == "pending")
                            .scalar_subquery()
                            .label("oldest_pending_at"),
                        )
                    )
                    .mappings()
                    .one()
                )
        except SQLAlchemyError:
            raise AnsvisAdapterError("EVENT_OPERATIONAL_STATUS_UNAVAILABLE") from None
        oldest_pending = cast(datetime | None, row["oldest_pending_at"])
        oldest_seconds = 0
        if oldest_pending is not None:
            oldest_seconds = max(0, int((current - _utc(oldest_pending)).total_seconds()))
        return EventOperationalSnapshot(
            accepted_receipts=int(row["accepted_receipts"]),
            pending_messages=int(row["pending_messages"]),
            published_messages=int(row["published_messages"]),
            failed_messages=int(row["failed_messages"]),
            retryable_attempts=int(row["retryable_attempts"]),
            quarantined_conflicts=int(row["quarantined_conflicts"]),
            delayed_messages=int(row["delayed_messages"]),
            oldest_pending_seconds=oldest_seconds,
        )
