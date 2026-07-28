"""Stable public Evidence Storage error mapping with resource concealment."""

from __future__ import annotations

from dataclasses import dataclass

from evidence_service.domain.errors import EvidenceError


@dataclass(frozen=True, slots=True)
class ErrorResponse:
    error_code: str
    message: str
    request_id: str


_PUBLIC = frozenset(
    {
        "EVIDENCE_NOT_FOUND",
        "EVIDENCE_NOT_AVAILABLE",
        "EVIDENCE_ACCESS_INVALID",
        "EVIDENCE_ACCESS_UNAVAILABLE",
        "EVIDENCE_URL_ISSUE_FAILED",
    }
)


def to_error_response(error: EvidenceError, request_id: str) -> ErrorResponse:
    if error.code in _PUBLIC:
        code = error.code
    elif error.code.endswith("_UNAVAILABLE"):
        code = "EVIDENCE_ACCESS_UNAVAILABLE"
    else:
        code = "EVIDENCE_NOT_FOUND"
    message = {
        "EVIDENCE_NOT_FOUND": "Evidence was not found.",
        "EVIDENCE_NOT_AVAILABLE": "Evidence is not available.",
        "EVIDENCE_ACCESS_INVALID": "Evidence access request is invalid.",
        "EVIDENCE_ACCESS_UNAVAILABLE": "Evidence access is temporarily unavailable.",
        "EVIDENCE_URL_ISSUE_FAILED": "Evidence access link could not be issued.",
    }[code]
    return ErrorResponse(error_code=code, message=message, request_id=request_id)
