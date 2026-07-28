"""Internal service boundary; trusted middleware must construct RequestContext."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from pydantic import ValidationError

from evidence_service.application.service import EvidenceApplicationService
from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.models import (
    AccessGrant,
    EvidenceObject,
    RequestContext,
    UploadTicket,
)
from evidence_service.schemas.commands import AccessRequestV1, UploadRequestV1


def request_upload(
    service: EvidenceApplicationService,
    payload: Mapping[str, object],
    context: RequestContext,
) -> UploadTicket:
    try:
        command = UploadRequestV1.model_validate(dict(payload)).command()
    except ValidationError:
        raise EvidenceError("EVIDENCE_REQUEST_INVALID") from None
    return service.request_upload(command, context)


def finalize_upload(
    service: EvidenceApplicationService,
    evidence_id: UUID,
    context: RequestContext,
) -> EvidenceObject:
    return service.finalize_upload(evidence_id, context)


def retry_upload(
    service: EvidenceApplicationService,
    evidence_id: UUID,
    context: RequestContext,
) -> UploadTicket:
    return service.retry_upload(evidence_id, context)


def record_clean_scan(
    service: EvidenceApplicationService,
    evidence_id: UUID,
    context: RequestContext,
) -> EvidenceObject:
    return service.record_scan_result(evidence_id, clean=True, context=context)


def request_access(
    service: EvidenceApplicationService,
    payload: Mapping[str, object],
    context: RequestContext,
) -> AccessGrant:
    try:
        command = AccessRequestV1.model_validate(dict(payload)).command()
    except ValidationError:
        raise EvidenceError("EVIDENCE_ACCESS_INVALID") from None
    return service.grant_access(command, context)
