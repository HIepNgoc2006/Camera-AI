"""Persistence ports for the Consent Service application boundary."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from consent_service.domain.models import (
    Consent,
    ConsentAuditIntent,
    ConsentChangeOutcome,
    ConsentEvent,
    ConsentTransitionRequest,
    Purpose,
    SubjectType,
    TrustedConsentContext,
)
from consent_service.domain.processing import ProcessingLookup


class ConsentRepository(Protocol):
    def register_purpose(self, purpose: Purpose) -> Purpose:
        """Insert one immutable purpose version."""

    def get_purpose(self, purpose_id: UUID, school_id: UUID) -> Purpose | None:
        """Return only a global or tenant-owned purpose."""

    def create_consent(
        self,
        consent: Consent,
        event: ConsentEvent,
        audit_intent: ConsentAuditIntent,
    ) -> ConsentChangeOutcome:
        """Atomically create consent, event, and audit intent or return an identical retry."""

    def transition_consent(
        self,
        request: ConsentTransitionRequest,
        context: TrustedConsentContext,
    ) -> ConsentChangeOutcome:
        """Atomically lock, authorize, transition, and append the change evidence."""

    def get_for_evaluation(
        self,
        consent_id: UUID,
        school_id: UUID,
    ) -> tuple[Consent | None, Purpose | None]:
        """Read a consent and its exact purpose with a mandatory tenant filter."""

    def find_for_processing(
        self,
        *,
        school_id: UUID,
        subject_type: SubjectType,
        subject_id: UUID | None,
        purpose_code: str,
    ) -> ProcessingLookup:
        """Return the bounded purpose/consent snapshot for one gate evaluation."""
