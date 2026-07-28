"""Notification intent acceptance with fresh batch authorization and minimized content."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic
from uuid import NAMESPACE_URL, UUID, uuid5

from camera_ai_audit import AuditIntent, IntentResult

from notification_service.application.ports import (
    AuthorizationBatchEvaluator,
    MetricsSink,
    NotificationRepository,
    NullMetricsSink,
)
from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    DeliveryState,
    NotificationIntent,
    NotificationOutcome,
    RecipientDelivery,
    TrustedSourceContext,
)
from notification_service.domain.policies import (
    authorize_recipient,
    authorize_source,
    render_generic,
)
from notification_service.schemas.commands import parse_notification_intent


def _fingerprint(command: Mapping[str, object]) -> bytes:
    # Idempotency is a transport concern. Excluding the key lets the repository
    # identify the same source-event/template replay even if a faulty producer
    # rotates its transport key.
    semantic = {key: value for key, value in command.items() if key != "idempotency_key"}
    canonical = json.dumps(semantic, default=str, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).digest()


def _audit_id(notification_id: UUID, recipient_id: UUID, suffix: str) -> UUID:
    return uuid5(notification_id, f"{recipient_id}:{suffix}")


class NotificationApplicationService:
    def __init__(
        self,
        repository: NotificationRepository,
        authorizer: AuthorizationBatchEvaluator,
        *,
        metrics: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        self._repository = repository
        self._authorizer = authorizer
        self._metrics = metrics or NullMetricsSink()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timer = timer

    def accept_intent(
        self,
        payload: Mapping[str, object],
        context: TrustedSourceContext,
    ) -> NotificationOutcome:
        command = parse_notification_intent(payload)
        authorize_source(command, context)
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")

        notification_id = uuid5(
            NAMESPACE_URL,
            f"camera-ai:notification:{command.tenant_id}:{command.idempotency_key}",
        )
        started = self._timer()
        try:
            authorizations = self._authorizer.evaluate(command)
        except Exception:
            self._increment("unavailable")
            raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE") from None
        self._observe(max(0.0, self._timer() - started))

        deliveries: list[RecipientDelivery] = []
        audit_intents: list[AuditIntent] = []
        denied = 0
        purpose_code = ""
        for recipient_ref in command.recipient_refs:
            for channel in command.channels:
                authorization = authorizations.get((recipient_ref, channel))
                try:
                    if authorization is None:
                        raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE")
                    _permission, purpose_code = authorize_recipient(
                        command, authorization, channel, now=now
                    )
                except NotificationError as error:
                    denied += 1
                    audit_intents.append(
                        self._audit(
                            action="NOTIFICATION_DISPATCH_DENIED",
                            result=IntentResult.DENIED,
                            notification_id=notification_id,
                            recipient_id=recipient_ref,
                            delivery_id=None,
                            purpose_code=authorization.purpose_code if authorization else "unknown",
                            request_id=command.request_id,
                            correlation_id=command.correlation_id,
                            occurred_at=now,
                            reason_code=error.code,
                            school_id=command.school_id,
                            suffix=f"{channel}:denied",
                        )
                    )
                    continue
                delivery_id = uuid5(notification_id, f"{recipient_ref}:{channel}")
                deliveries.append(
                    RecipientDelivery(
                        delivery_id=delivery_id,
                        notification_id=notification_id,
                        recipient_ref=recipient_ref,
                        channel=channel,
                        content=render_generic(
                            command,
                            channel,
                            str(notification_id),
                            created_at=now,
                        ),
                        state=DeliveryState.PENDING,
                        attempt_count=0,
                        next_attempt_at=None,
                        expires_at=command.notification_expires_at,
                        created_at=now,
                    )
                )
                audit_intents.append(
                    self._audit(
                        action="NOTIFICATION_DISPATCH_GRANTED",
                        result=IntentResult.SUCCESS,
                        notification_id=notification_id,
                        recipient_id=recipient_ref,
                        delivery_id=delivery_id,
                        purpose_code=purpose_code,
                        request_id=command.request_id,
                        correlation_id=command.correlation_id,
                        occurred_at=now,
                        reason_code=None,
                        school_id=command.school_id,
                        suffix=f"{channel}:granted",
                    )
                )

        intent = NotificationIntent(
            notification_id=notification_id,
            command=command,
            purpose_code=purpose_code or "notification_denied",
            policy_version=context.policy_version,
            created_at=now,
            state="pending" if deliveries else "denied",
        )
        outcome = self._repository.save_intent(
            intent=intent,
            deliveries=deliveries,
            audit_intents=audit_intents,
            content_fingerprint=_fingerprint(payload),
            denied_recipients=denied,
        )
        self._increment(
            "duplicate"
            if outcome.duplicate
            else ("queued" if outcome.queued_deliveries else "denied")
        )
        return outcome

    def _audit(
        self,
        *,
        action: str,
        result: IntentResult,
        notification_id: UUID,
        recipient_id: UUID,
        delivery_id: UUID | None,
        purpose_code: str,
        request_id: str,
        correlation_id: str,
        occurred_at: datetime,
        reason_code: str | None,
        school_id: UUID,
        suffix: str,
    ) -> AuditIntent:
        references = [
            ("notification_id", notification_id),
            ("recipient_id", recipient_id),
        ]
        if delivery_id is not None:
            references.append(("delivery_id", delivery_id))
        return AuditIntent(
            source_service="notification-service",
            source_event_id=_audit_id(notification_id, recipient_id, suffix),
            action=action,
            resource_type="notification_delivery",
            resource_id=delivery_id or notification_id,
            request_id=request_id,
            result=result,
            reason_code=reason_code,
            correlation_id=correlation_id,
            purpose_code=purpose_code,
            school_id=school_id,
            occurred_at=occurred_at,
            reference_ids=tuple(references),
            policy_versions=(
                ("notification_policy", "notification_privacy_policy_v1"),
                ("rbac_policy", "rbac_policy_v1"),
            ),
        )

    def _increment(self, outcome: str) -> None:
        with suppress(Exception):
            self._metrics.increment("notification_dispatch_total", outcome=outcome)

    def _observe(self, seconds: float) -> None:
        with suppress(Exception):
            self._metrics.observe("notification_reauthorization_seconds", seconds=seconds)
