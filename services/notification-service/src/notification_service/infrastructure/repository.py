"""PostgreSQL repository for atomic intent, delivery and audit-outbox writes."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from camera_ai_audit import AuditIntent
from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    Channel,
    ContentClass,
    DeliveryAttempt,
    DeliveryState,
    DeliveryWorkItem,
    NotificationCommand,
    NotificationIntent,
    NotificationOutcome,
    ProtectedEndpoint,
    RecipientDelivery,
    RenderedContent,
)
from notification_service.infrastructure.tables import (
    audit_outbox,
    delivery_attempts,
    notification_cancellations,
    notification_intents,
    recipient_deliveries,
    recipient_endpoints,
)

_UNFINISHED_STATES = (
    DeliveryState.PENDING.value,
    DeliveryState.CLAIMED.value,
    DeliveryState.RETRY_SCHEDULED.value,
    DeliveryState.DEAD_LETTERED.value,
)


class PostgresNotificationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save_intent(
        self,
        *,
        intent: NotificationIntent,
        deliveries: Sequence[RecipientDelivery],
        audit_intents: Sequence[AuditIntent],
        content_fingerprint: bytes,
        denied_recipients: int,
    ) -> NotificationOutcome:
        try:
            with self._engine.begin() as connection:
                existing = (
                    connection.execute(
                        sa.select(
                            notification_intents.c.notification_id,
                            notification_intents.c.content_fingerprint,
                        ).where(
                            sa.or_(
                                sa.and_(
                                    notification_intents.c.tenant_id == intent.command.tenant_id,
                                    notification_intents.c.idempotency_key
                                    == intent.command.idempotency_key,
                                ),
                                sa.and_(
                                    notification_intents.c.tenant_id == intent.command.tenant_id,
                                    notification_intents.c.source_event_id
                                    == intent.command.source_event_id,
                                    notification_intents.c.template_code
                                    == intent.command.template_code,
                                    notification_intents.c.template_version
                                    == intent.command.template_version,
                                ),
                            )
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing is not None:
                    if bytes(existing["content_fingerprint"]) != content_fingerprint:
                        raise NotificationError("NOTIFICATION_REQUEST_INVALID")
                    queued = connection.execute(
                        sa.select(sa.func.count())
                        .select_from(recipient_deliveries)
                        .where(
                            recipient_deliveries.c.notification_id == existing["notification_id"]
                        )
                    ).scalar_one()
                    return NotificationOutcome(
                        notification_id=existing["notification_id"],
                        queued_deliveries=int(queued),
                        denied_recipients=denied_recipients,
                        duplicate=True,
                    )
                connection.execute(
                    notification_intents.insert().values(
                        notification_id=intent.notification_id,
                        source_event_id=intent.command.source_event_id,
                        idempotency_key=intent.command.idempotency_key,
                        content_fingerprint=content_fingerprint,
                        tenant_id=intent.command.tenant_id,
                        school_id=intent.command.school_id,
                        subject_ref=intent.command.subject_ref,
                        resource_ref=intent.command.resource_ref,
                        content_class=intent.command.content_class.value,
                        template_code=intent.command.template_code,
                        template_version=intent.command.template_version,
                        purpose_code=intent.purpose_code,
                        policy_version=intent.policy_version,
                        source_state=intent.command.source_state,
                        source_expires_at=intent.command.source_expires_at,
                        expires_at=intent.command.notification_expires_at,
                        request_id=intent.command.request_id,
                        correlation_id=intent.command.correlation_id,
                        state=intent.state,
                        created_at=intent.created_at,
                    )
                )
                if deliveries:
                    connection.execute(
                        recipient_deliveries.insert(),
                        [
                            {
                                "delivery_id": delivery.delivery_id,
                                "notification_id": delivery.notification_id,
                                "recipient_ref": delivery.recipient_ref,
                                "channel": delivery.channel.value,
                                "rendered_content": dict(delivery.content.fields),
                                "state": delivery.state.value,
                                "attempt_count": delivery.attempt_count,
                                "next_attempt_at": delivery.next_attempt_at,
                                "expires_at": delivery.expires_at,
                                "claim_token": None,
                                "claim_until": None,
                                "created_at": delivery.created_at,
                                "updated_at": delivery.created_at,
                            }
                            for delivery in deliveries
                        ],
                    )
                if audit_intents:
                    connection.execute(
                        audit_outbox.insert(),
                        [
                            {
                                "audit_outbox_id": uuid5(
                                    NAMESPACE_URL,
                                    f"camera-ai:audit-outbox:{audit.source_service}:"
                                    f"{audit.source_event_id}",
                                ),
                                "source_service": audit.source_service,
                                "source_event_id": audit.source_event_id,
                                "school_id": audit.school_id,
                                "payload": audit.publisher_payload(),
                                "publish_status": "pending",
                                "attempt_count": 0,
                                "next_attempt_at": intent.created_at,
                                "claim_token": None,
                                "claim_expires_at": None,
                                "last_error_code": None,
                                "recorded_at": intent.created_at,
                                "delivered_at": None,
                            }
                            for audit in audit_intents
                        ],
                    )
                return NotificationOutcome(
                    notification_id=intent.notification_id,
                    queued_deliveries=len(deliveries),
                    denied_recipients=denied_recipients,
                    duplicate=False,
                )
        except NotificationError:
            raise
        except IntegrityError:
            # A concurrent equivalent insert can win after our initial lookup.
            # Re-read after the failed transaction so the loser returns the same
            # duplicate outcome instead of inviting an unsafe producer retry.
            try:
                with self._engine.connect() as connection:
                    existing = (
                        connection.execute(
                            sa.select(
                                notification_intents.c.notification_id,
                                notification_intents.c.content_fingerprint,
                            ).where(
                                sa.or_(
                                    sa.and_(
                                        notification_intents.c.tenant_id
                                        == intent.command.tenant_id,
                                        notification_intents.c.idempotency_key
                                        == intent.command.idempotency_key,
                                    ),
                                    sa.and_(
                                        notification_intents.c.tenant_id
                                        == intent.command.tenant_id,
                                        notification_intents.c.source_event_id
                                        == intent.command.source_event_id,
                                        notification_intents.c.template_code
                                        == intent.command.template_code,
                                        notification_intents.c.template_version
                                        == intent.command.template_version,
                                    ),
                                )
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if (
                        existing is None
                        or bytes(existing["content_fingerprint"]) != content_fingerprint
                    ):
                        raise NotificationError("NOTIFICATION_REQUEST_INVALID")
                    queued = connection.execute(
                        sa.select(sa.func.count())
                        .select_from(recipient_deliveries)
                        .where(
                            recipient_deliveries.c.notification_id == existing["notification_id"]
                        )
                    ).scalar_one()
                    return NotificationOutcome(
                        notification_id=existing["notification_id"],
                        queued_deliveries=int(queued),
                        denied_recipients=denied_recipients,
                        duplicate=True,
                    )
            except NotificationError:
                raise
            except Exception:
                raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    def save_endpoint(
        self,
        endpoint: ProtectedEndpoint,
        *,
        audit_intent: AuditIntent,
        recorded_at: datetime,
    ) -> None:
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    recipient_endpoints.insert().values(
                        endpoint_id=endpoint.endpoint_id,
                        tenant_id=endpoint.tenant_id,
                        recipient_ref=endpoint.recipient_ref,
                        kind=endpoint.kind.value,
                        endpoint_ciphertext=endpoint.ciphertext,
                        endpoint_lookup_digest=endpoint.lookup_digest,
                        state=endpoint.state.value,
                        verified_at=endpoint.verified_at,
                        revoked_at=None,
                        created_at=endpoint.created_at,
                    )
                )
                self._insert_audit(connection, audit_intent, recorded_at=recorded_at)
        except IntegrityError:
            raise NotificationError("NOTIFICATION_ENDPOINT_DENIED") from None
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    def load_delivery(self, delivery_id: UUID) -> DeliveryWorkItem | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(
                            *notification_intents.c,
                            recipient_deliveries.c.delivery_id,
                            recipient_deliveries.c.recipient_ref,
                            recipient_deliveries.c.channel,
                            recipient_deliveries.c.rendered_content,
                            recipient_deliveries.c.state.label("delivery_state"),
                            recipient_deliveries.c.attempt_count,
                            recipient_deliveries.c.next_attempt_at,
                            recipient_deliveries.c.expires_at.label("delivery_expires_at"),
                            recipient_deliveries.c.created_at.label("delivery_created_at"),
                        )
                        .select_from(
                            recipient_deliveries.join(
                                notification_intents,
                                recipient_deliveries.c.notification_id
                                == notification_intents.c.notification_id,
                            )
                        )
                        .where(recipient_deliveries.c.delivery_id == delivery_id)
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    return None
                channel = Channel(row["channel"])
                intent = self._intent_from_row(
                    row,
                    recipient_refs=(row["recipient_ref"],),
                    channels=(channel,),
                )
                delivery = RecipientDelivery(
                    delivery_id=row["delivery_id"],
                    notification_id=row["notification_id"],
                    recipient_ref=row["recipient_ref"],
                    channel=channel,
                    content=RenderedContent(channel=channel, fields=row["rendered_content"]),
                    state=DeliveryState(row["delivery_state"]),
                    attempt_count=row["attempt_count"],
                    next_attempt_at=row["next_attempt_at"],
                    expires_at=row["delivery_expires_at"],
                    created_at=row["delivery_created_at"],
                )
                return DeliveryWorkItem(intent=intent, delivery=delivery)
        except NotificationError:
            raise
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    def load_notification(self, notification_id: UUID) -> NotificationIntent | None:
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        sa.select(notification_intents).where(
                            notification_intents.c.notification_id == notification_id
                        )
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    return None
                delivery_rows = (
                    connection.execute(
                        sa.select(
                            recipient_deliveries.c.recipient_ref,
                            recipient_deliveries.c.channel,
                        ).where(recipient_deliveries.c.notification_id == notification_id)
                    )
                    .mappings()
                    .all()
                )
                recipients = tuple(dict.fromkeys(item["recipient_ref"] for item in delivery_rows))
                channels = tuple(dict.fromkeys(Channel(item["channel"]) for item in delivery_rows))
                return self._intent_from_row(
                    row,
                    recipient_refs=recipients or (row["subject_ref"],),
                    channels=channels or (Channel.IN_APP,),
                )
        except NotificationError:
            raise
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    def append_audit(self, audit_intent: AuditIntent, *, recorded_at: datetime) -> None:
        try:
            with self._engine.begin() as connection:
                self._insert_audit(connection, audit_intent, recorded_at=recorded_at)
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    def record_attempt(
        self,
        *,
        work_item: DeliveryWorkItem,
        attempt: DeliveryAttempt,
        next_state: DeliveryState,
        audit_intent: AuditIntent,
    ) -> bool:
        try:
            with self._engine.begin() as connection:
                current = (
                    connection.execute(
                        sa.select(
                            recipient_deliveries.c.state,
                            recipient_deliveries.c.attempt_count,
                        )
                        .where(recipient_deliveries.c.delivery_id == work_item.delivery.delivery_id)
                        .with_for_update()
                    )
                    .mappings()
                    .first()
                )
                if (
                    current is None
                    or current["state"] not in _UNFINISHED_STATES
                    or current["attempt_count"] != work_item.delivery.attempt_count
                    or attempt.attempt_number != current["attempt_count"] + 1
                ):
                    return False
                connection.execute(
                    delivery_attempts.insert().values(
                        attempt_id=attempt.attempt_id,
                        delivery_id=attempt.delivery_id,
                        attempt_number=attempt.attempt_number,
                        result=attempt.result.value,
                        provider_result_category=attempt.stable_provider_result_category,
                        occurred_at=attempt.occurred_at,
                        next_attempt_at=attempt.next_attempt_at,
                    )
                )
                connection.execute(
                    recipient_deliveries.update()
                    .where(recipient_deliveries.c.delivery_id == work_item.delivery.delivery_id)
                    .values(
                        state=next_state.value,
                        attempt_count=attempt.attempt_number,
                        next_attempt_at=attempt.next_attempt_at,
                        claim_token=None,
                        claim_until=None,
                        updated_at=attempt.occurred_at,
                    )
                )
                self._insert_audit(connection, audit_intent, recorded_at=attempt.occurred_at)
                return True
        except IntegrityError:
            return False
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    def cancel_notification(
        self,
        *,
        notification_id: UUID,
        trigger_code: str,
        owner_service: str,
        request_id: str,
        occurred_at: datetime,
        audit_intent: AuditIntent,
    ) -> int:
        cancellation_id = uuid5(notification_id, f"cancellation:{trigger_code}")
        try:
            with self._engine.begin() as connection:
                inserted = connection.execute(
                    pg_insert(notification_cancellations)
                    .values(
                        cancellation_id=cancellation_id,
                        notification_id=notification_id,
                        trigger_code=trigger_code,
                        owner_service=owner_service,
                        recipient_ref=None,
                        channel=None,
                        request_id=request_id,
                        occurred_at=occurred_at,
                    )
                    .on_conflict_do_nothing(index_elements=["cancellation_id"])
                )
                if inserted.rowcount == 0:
                    return 0
                update = connection.execute(
                    recipient_deliveries.update()
                    .where(
                        recipient_deliveries.c.notification_id == notification_id,
                        recipient_deliveries.c.state.in_(_UNFINISHED_STATES),
                    )
                    .values(
                        state=DeliveryState.CANCELLED.value,
                        next_attempt_at=None,
                        claim_token=None,
                        claim_until=None,
                        updated_at=occurred_at,
                    )
                )
                connection.execute(
                    notification_intents.update()
                    .where(notification_intents.c.notification_id == notification_id)
                    .values(state="cancelled")
                )
                self._insert_audit(connection, audit_intent, recorded_at=occurred_at)
                return int(update.rowcount)
        except IntegrityError:
            return 0
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    def revoke_endpoint(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        occurred_at: datetime,
        audit_intent: AuditIntent,
    ) -> bool:
        try:
            with self._engine.begin() as connection:
                revoked = connection.execute(
                    recipient_endpoints.update()
                    .where(
                        recipient_endpoints.c.endpoint_id == endpoint_id,
                        recipient_endpoints.c.tenant_id == tenant_id,
                        recipient_endpoints.c.recipient_ref == recipient_ref,
                        recipient_endpoints.c.state == "active",
                    )
                    .values(state="revoked", revoked_at=occurred_at)
                )
                if revoked.rowcount != 1:
                    return False
                matching_deliveries = (
                    connection.execute(
                        sa.select(
                            recipient_deliveries.c.notification_id,
                            recipient_deliveries.c.channel,
                        )
                        .select_from(
                            recipient_deliveries.join(
                                notification_intents,
                                recipient_deliveries.c.notification_id
                                == notification_intents.c.notification_id,
                            )
                        )
                        .where(
                            notification_intents.c.tenant_id == tenant_id,
                            recipient_deliveries.c.recipient_ref == recipient_ref,
                            recipient_deliveries.c.channel != Channel.IN_APP.value,
                        )
                    )
                    .mappings()
                    .all()
                )
                for delivery in matching_deliveries:
                    connection.execute(
                        pg_insert(notification_cancellations)
                        .values(
                            cancellation_id=uuid5(
                                delivery["notification_id"],
                                f"cancellation:endpoint_revoked:{recipient_ref}:"
                                f"{delivery['channel']}",
                            ),
                            notification_id=delivery["notification_id"],
                            trigger_code="endpoint_revoked",
                            owner_service="notification-service",
                            recipient_ref=recipient_ref,
                            channel=delivery["channel"],
                            request_id=audit_intent.request_id,
                            occurred_at=occurred_at,
                        )
                        .on_conflict_do_nothing(index_elements=["cancellation_id"])
                    )
                matching_intents = sa.select(notification_intents.c.notification_id).where(
                    notification_intents.c.tenant_id == tenant_id
                )
                connection.execute(
                    recipient_deliveries.update()
                    .where(
                        recipient_deliveries.c.notification_id.in_(matching_intents),
                        recipient_deliveries.c.recipient_ref == recipient_ref,
                        recipient_deliveries.c.channel != Channel.IN_APP.value,
                        recipient_deliveries.c.state.in_(_UNFINISHED_STATES),
                    )
                    .values(
                        state=DeliveryState.CANCELLED.value,
                        next_attempt_at=None,
                        claim_token=None,
                        claim_until=None,
                        updated_at=occurred_at,
                    )
                )
                self._insert_audit(connection, audit_intent, recorded_at=occurred_at)
                return True
        except Exception:
            raise NotificationError("NOTIFICATION_DELIVERY_UNAVAILABLE") from None

    @staticmethod
    def _intent_from_row(
        row: sa.RowMapping,
        *,
        recipient_refs: tuple[UUID, ...],
        channels: tuple[Channel, ...],
    ) -> NotificationIntent:
        command = NotificationCommand(
            source_event_id=row["source_event_id"],
            idempotency_key=row["idempotency_key"],
            tenant_id=row["tenant_id"],
            school_id=row["school_id"],
            subject_ref=row["subject_ref"],
            resource_ref=row["resource_ref"],
            content_class=ContentClass(row["content_class"]),
            template_code=row["template_code"],
            template_version=row["template_version"],
            source_state=row["source_state"],
            source_expires_at=row["source_expires_at"],
            notification_expires_at=row["expires_at"],
            recipient_refs=recipient_refs,
            channels=channels,
            request_id=row["request_id"],
            correlation_id=row["correlation_id"],
        )
        return NotificationIntent(
            notification_id=row["notification_id"],
            command=command,
            purpose_code=row["purpose_code"],
            policy_version=row["policy_version"],
            created_at=row["created_at"],
            state=row["state"],
        )

    @staticmethod
    def _insert_audit(
        connection: sa.Connection,
        audit: AuditIntent,
        *,
        recorded_at: datetime,
    ) -> None:
        connection.execute(
            pg_insert(audit_outbox)
            .values(
                audit_outbox_id=uuid5(
                    NAMESPACE_URL,
                    f"camera-ai:audit-outbox:{audit.source_service}:{audit.source_event_id}",
                ),
                source_service=audit.source_service,
                source_event_id=audit.source_event_id,
                school_id=audit.school_id,
                payload=audit.publisher_payload(),
                publish_status="pending",
                attempt_count=0,
                next_attempt_at=recorded_at,
                claim_token=None,
                claim_expires_at=None,
                last_error_code=None,
                recorded_at=recorded_at,
                delivered_at=None,
            )
            .on_conflict_do_nothing(index_elements=["source_service", "source_event_id"])
        )
