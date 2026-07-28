"""Freshly authorized delivery, retry, open and cancellation transitions."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid5

from camera_ai_audit import AuditIntent, IntentResult

from notification_service.application.ports import (
    AuthorizationBatchEvaluator,
    DeliveryLifecycleRepository,
    MetricsSink,
    NullMetricsSink,
)
from notification_service.domain.errors import NotificationError
from notification_service.domain.models import (
    AttemptResult,
    Channel,
    DeadLetterEnvelope,
    DeliveryAttempt,
    DeliveryState,
    DeliveryWorkItem,
    OpenGrant,
    ProviderResultCategory,
    TrustedSourceContext,
)
from notification_service.domain.policies import (
    authorize_recipient,
    authorize_source,
    can_cancel,
    retry_schedule,
)

_RETRYABLE = frozenset(
    {
        ProviderResultCategory.TEMPORARY_UNAVAILABLE,
        ProviderResultCategory.RATE_LIMITED,
    }
)
_UNFINISHED = frozenset(
    {
        DeliveryState.PENDING,
        DeliveryState.CLAIMED,
        DeliveryState.RETRY_SCHEDULED,
        DeliveryState.DEAD_LETTERED,
    }
)
_CANCELLATION_TRIGGER_BY_ERROR = {
    "NOTIFICATION_CONSENT_DENIED": "consent_withdrawn",
    "NOTIFICATION_PERMISSION_DENIED": "permission_revoked",
    "NOTIFICATION_RECIPIENT_SCOPE_DENIED": "relationship_revoked",
    "NOTIFICATION_ENDPOINT_DENIED": "endpoint_revoked",
    "NOTIFICATION_SOURCE_NOT_ELIGIBLE": "source_rejected",
    "NOTIFICATION_EXPIRED": "source_expired",
    "NOTIFICATION_PURPOSE_DENIED": "purpose_ended",
}


class DeliveryApplicationService:
    """Provider-neutral lifecycle; real provider dispatch remains out of scope."""

    def __init__(
        self,
        repository: DeliveryLifecycleRepository,
        authorizer: AuthorizationBatchEvaluator,
        *,
        metrics: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
        timer: Callable[[], float] = monotonic,
        jitter: Callable[[int], int] = lambda _maximum: 0,
    ) -> None:
        self._repository = repository
        self._authorizer = authorizer
        self._metrics = metrics or NullMetricsSink()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timer = timer
        self._jitter = jitter

    def record_provider_result(
        self,
        *,
        delivery_id: UUID,
        category: ProviderResultCategory,
        retry_backlog: int,
    ) -> DeadLetterEnvelope | None:
        """Re-authorize, then append one controlled attempt and state transition."""

        try:
            work_item = self._require_current_authorization(delivery_id)
        except NotificationError as error:
            self._stop_stale_delivery(delivery_id, error)
            raise
        delivery = work_item.delivery
        now = self._now()
        if delivery.state not in _UNFINISHED:
            raise NotificationError("NOTIFICATION_NOT_AVAILABLE")
        if now >= delivery.expires_at:
            raise NotificationError("NOTIFICATION_EXPIRED")
        with suppress(Exception):
            self._metrics.set_gauge(
                "notification_retry_backlog_messages",
                value=float(retry_backlog),
            )

        attempt_number = delivery.attempt_count + 1
        if attempt_number > 5:
            raise NotificationError("NOTIFICATION_RETRY_DENIED")

        next_attempt_at = None
        if category is ProviderResultCategory.ACCEPTED:
            result = AttemptResult.DELIVERED
            next_state = DeliveryState.DELIVERED
            action = "NOTIFICATION_DELIVERED"
        elif category in _RETRYABLE:
            next_attempt_at = retry_schedule(
                attempt_count=delivery.attempt_count,
                now=now,
                expires_at=delivery.expires_at,
                retry_backlog=retry_backlog,
                jitter=self._jitter,
            )
            if next_attempt_at is not None:
                result = AttemptResult.RETRY_SCHEDULED
                next_state = DeliveryState.RETRY_SCHEDULED
                action = "NOTIFICATION_RETRY_SCHEDULED"
            else:
                result = AttemptResult.DEAD_LETTERED
                next_state = DeliveryState.DEAD_LETTERED
                action = "NOTIFICATION_DEAD_LETTERED"
        else:
            result = AttemptResult.DEAD_LETTERED
            next_state = DeliveryState.DEAD_LETTERED
            action = "NOTIFICATION_DEAD_LETTERED"

        attempt = DeliveryAttempt(
            attempt_id=uuid5(delivery.delivery_id, f"attempt:{attempt_number}"),
            delivery_id=delivery.delivery_id,
            attempt_number=attempt_number,
            result=result,
            stable_provider_result_category=category.value,
            occurred_at=now,
            next_attempt_at=next_attempt_at,
        )
        updated = self._repository.record_attempt(
            work_item=work_item,
            attempt=attempt,
            next_state=next_state,
            audit_intent=self._audit(
                work_item,
                action=action,
                result=IntentResult.SUCCESS,
                reason_code=None,
                occurred_at=now,
                suffix=f"attempt:{attempt_number}:{result.value}",
            ),
        )
        if not updated:
            raise NotificationError("NOTIFICATION_NOT_AVAILABLE")
        self._metric(
            {
                DeliveryState.DELIVERED: "delivered",
                DeliveryState.RETRY_SCHEDULED: "retry_scheduled",
                DeliveryState.DEAD_LETTERED: "dead_lettered",
            }[next_state]
        )
        if next_state is not DeliveryState.DEAD_LETTERED:
            return None
        with suppress(Exception):
            self._metrics.increment("notification_dlq_arrivals_total", outcome="arrived")
        return DeadLetterEnvelope(
            delivery_id=delivery.delivery_id,
            notification_id=delivery.notification_id,
            attempt_count=attempt_number,
            reason_category=category,
            occurred_at=now,
        )

    def authorize_open(self, *, delivery_id: UUID, recipient_ref: UUID) -> OpenGrant:
        """Return opaque navigation data only after a current object-level check."""

        try:
            authorized_work_item = self._require_current_authorization(delivery_id)
            if (
                authorized_work_item.delivery.channel is not Channel.IN_APP
                or authorized_work_item.delivery.recipient_ref != recipient_ref
                or authorized_work_item.delivery.state
                in {DeliveryState.CANCELLED, DeliveryState.EXPIRED, DeliveryState.DEAD_LETTERED}
            ):
                raise NotificationError("NOTIFICATION_NOT_AVAILABLE")
        except NotificationError as error:
            denied_work_item = self._repository.load_delivery(delivery_id)
            if denied_work_item is not None:
                self._repository.append_audit(
                    self._audit(
                        denied_work_item,
                        action="NOTIFICATION_OPEN_DENIED",
                        result=IntentResult.DENIED,
                        reason_code=error.code,
                        occurred_at=self._now(),
                        suffix=f"open-denied:{recipient_ref}",
                    ),
                    recorded_at=self._now(),
                )
            raise NotificationError("NOTIFICATION_NOT_AVAILABLE") from None

        now = self._now()
        self._repository.append_audit(
            self._audit(
                authorized_work_item,
                action="NOTIFICATION_OPEN_GRANTED",
                result=IntentResult.SUCCESS,
                reason_code=None,
                occurred_at=now,
                suffix=f"open-granted:{recipient_ref}",
            ),
            recorded_at=now,
        )
        return OpenGrant(
            notification_id=authorized_work_item.intent.notification_id,
            resource_ref=authorized_work_item.intent.command.resource_ref,
            template_code=authorized_work_item.intent.command.template_code,
        )

    def cancel(
        self,
        *,
        notification_id: UUID,
        trigger_code: str,
        context: TrustedSourceContext,
    ) -> int:
        """Idempotently cancel stale work after authenticating the owning source."""

        if not can_cancel(trigger_code):
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")
        intent = self._repository.load_notification(notification_id)
        if intent is None:
            raise NotificationError("NOTIFICATION_NOT_AVAILABLE")
        authorize_source(intent.command, context)
        now = self._now()
        audit = AuditIntent(
            source_service="notification-service",
            source_event_id=uuid5(notification_id, f"cancel:{trigger_code}"),
            action="NOTIFICATION_CANCELLED",
            result=IntentResult.SUCCESS,
            resource_type="notification_delivery",
            resource_id=notification_id,
            request_id=intent.command.request_id,
            correlation_id=intent.command.correlation_id,
            purpose_code=intent.purpose_code,
            school_id=intent.command.school_id,
            occurred_at=now,
            reference_ids=(("notification_id", notification_id),),
            policy_versions=(
                ("notification_policy", intent.policy_version),
                ("rbac_policy", "rbac_policy_v1"),
            ),
        )
        cancelled = self._repository.cancel_notification(
            notification_id=notification_id,
            trigger_code=trigger_code,
            owner_service=context.source_service,
            request_id=intent.command.request_id,
            occurred_at=now,
            audit_intent=audit,
        )
        if cancelled:
            self._metric("cancelled")
        return cancelled

    def _require_current_authorization(self, delivery_id: UUID) -> DeliveryWorkItem:
        work_item = self._repository.load_delivery(delivery_id)
        if work_item is None:
            raise NotificationError("NOTIFICATION_NOT_AVAILABLE")
        started = self._timer()
        try:
            decisions = self._authorizer.evaluate(work_item.intent.command)
            authorization = decisions.get(
                (work_item.delivery.recipient_ref, work_item.delivery.channel)
            )
            if authorization is None:
                raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE")
            authorize_recipient(
                work_item.intent.command,
                authorization,
                work_item.delivery.channel,
                now=self._now(),
            )
        except NotificationError:
            raise
        except Exception:
            raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE") from None
        finally:
            with suppress(Exception):
                self._metrics.observe(
                    "notification_reauthorization_seconds",
                    seconds=max(0.0, self._timer() - started),
                )
        return work_item

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise NotificationError("NOTIFICATION_REQUEST_INVALID")
        return now

    def _audit(
        self,
        work_item: DeliveryWorkItem,
        *,
        action: str,
        result: IntentResult,
        reason_code: str | None,
        occurred_at: datetime,
        suffix: str,
    ) -> AuditIntent:
        command = work_item.intent.command
        return AuditIntent(
            source_service="notification-service",
            source_event_id=uuid5(work_item.intent.notification_id, suffix),
            action=action,
            resource_type="notification_delivery",
            resource_id=work_item.delivery.delivery_id,
            request_id=command.request_id,
            result=result,
            reason_code=reason_code,
            correlation_id=command.correlation_id,
            purpose_code=work_item.intent.purpose_code,
            school_id=command.school_id,
            occurred_at=occurred_at,
            reference_ids=(
                ("notification_id", work_item.intent.notification_id),
                ("recipient_id", work_item.delivery.recipient_ref),
                ("delivery_id", work_item.delivery.delivery_id),
            ),
            policy_versions=(
                ("notification_policy", work_item.intent.policy_version),
                ("rbac_policy", "rbac_policy_v1"),
            ),
        )

    def _metric(self, outcome: str) -> None:
        with suppress(Exception):
            self._metrics.increment("notification_dispatch_total", outcome=outcome)

    def _stop_stale_delivery(
        self,
        delivery_id: UUID,
        error: NotificationError,
    ) -> None:
        work_item = self._repository.load_delivery(delivery_id)
        if work_item is None:
            return
        now = self._now()
        self._repository.append_audit(
            self._audit(
                work_item,
                action="NOTIFICATION_DISPATCH_DENIED",
                result=IntentResult.DENIED,
                reason_code=error.code,
                occurred_at=now,
                suffix=f"dispatch-denied:{error.code}",
            ),
            recorded_at=now,
        )
        trigger = _CANCELLATION_TRIGGER_BY_ERROR.get(error.code)
        if trigger is None:
            self._metric("unavailable")
            return
        cancelled = self._repository.cancel_notification(
            notification_id=work_item.intent.notification_id,
            trigger_code=trigger,
            owner_service="notification-service",
            request_id=work_item.intent.command.request_id,
            occurred_at=now,
            audit_intent=self._audit(
                work_item,
                action="NOTIFICATION_CANCELLED",
                result=IntentResult.SUCCESS,
                reason_code=None,
                occurred_at=now,
                suffix=f"automatic-cancel:{trigger}",
            ),
        )
        if cancelled:
            self._metric("cancelled")
        self._metric("denied")
