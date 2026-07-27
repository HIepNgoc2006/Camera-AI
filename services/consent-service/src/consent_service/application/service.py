"""Trusted-context Consent Service use cases."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from consent_service.application.ports import ConsentRepository
from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    Consent,
    ConsentAuditIntent,
    ConsentChangeOutcome,
    ConsentDecision,
    ConsentEvent,
    ConsentEventType,
    ConsentStatus,
    ConsentTransitionRequest,
    Purpose,
    PurposeStatus,
    TrustedConsentContext,
    TrustedEvaluationContext,
    TrustedProcessingContext,
    TrustedPurposeContext,
)
from consent_service.domain.policies import AUDIT_ACTIONS, evaluate_consent
from consent_service.domain.processing import (
    PROCESSING_PURPOSES,
    ProcessingConsentDecision,
    ProcessingLookup,
    decide_processing,
    resolve_subject,
)
from consent_service.schemas.commands import (
    EvaluateConsentV1,
    EvaluateProcessingV1,
    parse_evaluate_consent,
    parse_evaluate_processing,
    parse_register_purpose,
    parse_request_consent,
    parse_transition_consent,
)

Clock = Callable[[], datetime]
IdentifierFactory = Callable[[], UUID]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _event_type(status: ConsentStatus) -> ConsentEventType:
    return ConsentEventType(status.value)


class ConsentApplicationService:
    """Register purposes, record consent changes, and evaluate exact processing scope."""

    def __init__(
        self,
        repository: ConsentRepository,
        *,
        clock: Clock = _utc_now,
        identifier_factory: IdentifierFactory = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifier_factory = identifier_factory

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ConsentError("CONSENT_INPUT_INVALID")
        return value

    def _id(self) -> UUID:
        value = self._identifier_factory()
        if value.int == 0:
            raise ConsentError("CONSENT_INPUT_INVALID")
        return value

    def register_purpose(
        self,
        payload: Mapping[str, object],
        context: TrustedPurposeContext,
    ) -> Purpose:
        if not context.can_manage_purposes:
            raise ConsentError("CONSENT_AUTHORITY_DENIED")
        item = parse_register_purpose(payload)
        now = self._now()
        purpose = Purpose(
            purpose_id=self._id(),
            school_id=context.school_id,
            code=item.code,
            description=item.description,
            data_categories=tuple(item.data_categories),
            requires_biometric_consent=item.requires_biometric_consent,
            status=PurposeStatus(item.status),
            version=item.version,
            valid_from=item.valid_from,
            valid_to=item.valid_to,
            created_at=now,
        )
        return self._repository.register_purpose(purpose)

    def request_consent(
        self,
        payload: Mapping[str, object],
        context: TrustedConsentContext,
    ) -> ConsentChangeOutcome:
        item = parse_request_consent(payload)
        if not context.authority_verified:
            raise ConsentError("CONSENT_AUTHORITY_DENIED")
        if (
            item.subject_type is not context.subject_type
            or item.subject_id != context.subject_id
            or item.authority_type is not context.authority_type
            or item.authority_ref != context.authority_ref
        ):
            raise ConsentError("CONSENT_AUTHORITY_DENIED")
        now = self._now()
        purpose = self._repository.get_purpose(item.purpose_id, context.school_id)
        if purpose is None or not purpose.is_active_at(now, context.school_id):
            raise ConsentError("CONSENT_PURPOSE_INACTIVE")
        if not set(item.scope_codes).issubset(purpose.data_categories):
            raise ConsentError("CONSENT_INPUT_INVALID")

        consent_id = self._id()
        event_id = self._id()
        audit_intent_id = self._id()
        consent = Consent(
            consent_id=consent_id,
            school_id=context.school_id,
            subject_type=context.subject_type,
            subject_id=context.subject_id,
            purpose_id=purpose.purpose_id,
            authority_type=context.authority_type,
            authority_ref=context.authority_ref,
            status=ConsentStatus.PENDING,
            scope_codes=tuple(item.scope_codes),
            valid_from=item.valid_from,
            valid_to=item.valid_to,
            withdrawn_at=None,
            restricted_at=None,
            policy_version=item.policy_version,
            created_at=now,
            updated_at=now,
            row_version=1,
        )
        event = ConsentEvent(
            consent_event_id=event_id,
            school_id=context.school_id,
            consent_id=consent_id,
            event_type=ConsentEventType.REQUESTED,
            actor_id=context.actor_id,
            reason_code=None,
            request_id=item.request_id,
            evidence_ref=item.evidence_ref,
            idempotency_key=item.idempotency_key,
            request_fingerprint=item.fingerprint(),
            resulting_version=1,
            occurred_at=now,
            recorded_at=now,
        )
        intent = ConsentAuditIntent(
            audit_intent_id=audit_intent_id,
            consent_event_id=event_id,
            source_event_id=event_id,
            school_id=context.school_id,
            actor_id=context.actor_id,
            action=AUDIT_ACTIONS[event.event_type],
            purpose_code=purpose.code,
            resource_id=consent_id,
            request_id=item.request_id,
            result="success",
            reason_code=None,
            state_before=None,
            state_after=ConsentStatus.PENDING.value,
            policy_version=item.policy_version,
            created_at=now,
        )
        return self._repository.create_consent(consent, event, intent)

    def transition_consent(
        self,
        payload: Mapping[str, object],
        context: TrustedConsentContext,
    ) -> ConsentChangeOutcome:
        item = parse_transition_consent(payload)
        if not context.authority_verified:
            raise ConsentError("CONSENT_AUTHORITY_DENIED")
        now = self._now()
        request = ConsentTransitionRequest(
            consent_id=item.consent_id,
            target_status=ConsentStatus(item.target_status),
            expected_version=item.expected_version,
            reason_code=item.reason_code,
            request_id=item.request_id,
            evidence_ref=item.evidence_ref,
            idempotency_key=item.idempotency_key,
            request_fingerprint=item.fingerprint(),
            consent_event_id=self._id(),
            audit_intent_id=self._id(),
            changed_at=now,
        )
        return self._repository.transition_consent(request, context)

    def evaluate(
        self,
        payload: Mapping[str, object],
        context: TrustedEvaluationContext,
    ) -> ConsentDecision:
        item: EvaluateConsentV1 = parse_evaluate_consent(payload)
        consent, purpose = self._repository.get_for_evaluation(
            item.consent_id,
            context.school_id,
        )
        return evaluate_consent(
            consent,
            purpose,
            context=context,
            expected_purpose_id=item.purpose_id,
            required_scope_codes=tuple(item.required_scope_codes),
            expected_version=item.expected_version,
            evaluated_at=self._now(),
        )

    def evaluate_processing(
        self,
        payload: Mapping[str, object],
        context: TrustedProcessingContext,
    ) -> ProcessingConsentDecision:
        """Issue #139 internal gate: strict tri-state output, deny on ambiguity.

        Only repository unavailability escapes as ``CONSENT_UNAVAILABLE`` so the
        ingestion caller can defer with a durable receipt; every evaluated
        condition returns a decision. The subject reference is event data and
        therefore resolves fail-closed instead of raising.
        """

        if not context.gate_authorized:
            raise ConsentError("CONSENT_AUTHORITY_DENIED")
        item: EvaluateProcessingV1 = parse_evaluate_processing(payload)
        subject_id = resolve_subject(item.subject_ref)
        mapping = PROCESSING_PURPOSES.get(item.purpose)
        if mapping is None:
            lookup = ProcessingLookup(purposes=(), consents=())
        else:
            lookup = self._repository.find_for_processing(
                school_id=context.school_id,
                subject_type=mapping.subject_type,
                subject_id=subject_id,
                purpose_code=mapping.code,
            )
        return decide_processing(
            lookup,
            school_id=context.school_id,
            subject_id=subject_id,
            purpose_code=item.purpose,
            gate_policy_version=item.policy_version,
            evaluated_at=self._now(),
        )
