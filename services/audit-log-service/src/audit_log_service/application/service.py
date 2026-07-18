"""AppendAuditEvent use case with trusted-context enforcement."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from audit_log_service.application.ports import AuditRepository
from audit_log_service.domain.errors import AuditError
from audit_log_service.domain.integrity import IntegritySigner
from audit_log_service.domain.models import (
    AppendOutcome,
    AuditChanges,
    AuditEvent,
    TrustedAuditContext,
)
from audit_log_service.domain.policies import validate_action_policy
from audit_log_service.schemas.events import parse_audit_event

Clock = Callable[[], datetime]
IdentifierFactory = Callable[[], UUID]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AppendAuditEventService:
    """Validate, bind trusted context, and append immutable audit evidence."""

    def __init__(
        self,
        repository: AuditRepository,
        signer: IntegritySigner,
        *,
        clock: Clock = _utc_now,
        identifier_factory: IdentifierFactory = uuid4,
    ) -> None:
        self._repository = repository
        self._signer = signer
        self._clock = clock
        self._identifier_factory = identifier_factory

    def append(
        self,
        payload: Mapping[str, object],
        context: TrustedAuditContext,
    ) -> AppendOutcome:
        publisher = parse_audit_event(payload)
        if publisher.source_service != context.source_service:
            raise AuditError("AUDIT_EVENT_INVALID")

        event = AuditEvent(
            event_schema_version=publisher.event_schema_version,
            source_service=context.source_service,
            source_event_id=publisher.source_event_id,
            correlation_id=publisher.correlation_id,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            actor_role=context.actor_role,
            school_id=context.school_id,
            action=publisher.action,
            purpose_code=publisher.purpose_code,
            resource_type=publisher.resource_type,
            resource_id=publisher.resource_id,
            resource_ref=publisher.resource_ref,
            request_id=publisher.request_id,
            result=publisher.result,
            reason_code=publisher.reason_code,
            ip_prefix=publisher.network(),
            user_agent_family=publisher.user_agent_family,
            changes=(
                publisher.changes.to_domain() if publisher.changes is not None else AuditChanges()
            ),
            occurred_at=publisher.occurred_at,
            retention_until=context.retention_until,
        )
        validate_action_policy(event)

        recorded_at = self._clock()
        if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
            raise AuditError("AUDIT_EVENT_INVALID")
        if context.retention_until <= recorded_at:
            raise AuditError("AUDIT_EVENT_INVALID")
        audit_event_id = self._identifier_factory()
        if audit_event_id.int == 0:
            raise AuditError("AUDIT_EVENT_INVALID")
        return self._repository.append(
            event,
            recorded_at=recorded_at,
            audit_event_id=audit_event_id,
            signer=self._signer,
        )
