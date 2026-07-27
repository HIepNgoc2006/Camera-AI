"""In-process consent gate composition over the Consent Service evaluation port.

Mirrors the worker's audit delivery composition: the adapter process loads the
consent-service application code with its own engine against the ``privacy``
schema owner — no cross-schema SQL, no shared session. Every failure collapses
to ``EVENT_CONSENT_UNAVAILABLE`` so ingestion defers with a durable receipt
instead of guessing a consent status.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from ansvis_adapter.application.ports import ConsentGate
from ansvis_adapter.domain.consent import (
    CONSENT_UNAVAILABLE,
    ConsentGateDecision,
    ConsentGateRequest,
    ConsentGateStatus,
)
from ansvis_adapter.domain.errors import AnsvisAdapterError

GATE_SOURCE_SERVICE = "event-ingestion-service"


class ConsentServiceGate(ConsentGate):
    """Evaluate one request through the trusted consent-service processing port."""

    def __init__(self, engine: Engine) -> None:
        from consent_service.application.service import ConsentApplicationService
        from consent_service.infrastructure.repository import SqlAlchemyConsentRepository

        self._service = ConsentApplicationService(SqlAlchemyConsentRepository(engine))

    def evaluate(self, request: ConsentGateRequest) -> ConsentGateDecision:
        from consent_service.domain.models import TrustedProcessingContext

        try:
            decision = self._service.evaluate_processing(
                {
                    "schema_version": 1,
                    "tenant_ref": request.tenant_ref,
                    "school_ref": request.school_ref,
                    "subject_ref": request.subject_ref,
                    "purpose": request.purpose_code,
                    "policy_version": request.policy_version,
                },
                TrustedProcessingContext(
                    school_id=request.school_id,
                    source_service=GATE_SOURCE_SERVICE,
                    gate_authorized=True,
                ),
            )
            return ConsentGateDecision(
                status=ConsentGateStatus(decision.status.value),
                reason_code=decision.reason_code,
                policy_version=decision.policy_version,
            )
        except Exception:
            raise AnsvisAdapterError(CONSENT_UNAVAILABLE) from None
