"""Stable API error mapping."""

from dataclasses import dataclass

from report_service.domain.errors import ReportError


@dataclass(frozen=True, slots=True)
class ErrorResponse:
    error_code: str
    message: str
    request_id: str
    status_code: int
    retry_after_seconds: int | None = None


def map_error(error: ReportError, request_id: str) -> ErrorResponse:
    status = (
        429
        if error.code == "REPORT_EXPORT_QUOTA_EXCEEDED"
        else 503
        if error.code.endswith("UNAVAILABLE")
        else 404
        if error.code in {"REPORT_NOT_FOUND", "REPORT_EXPORT_NOT_AVAILABLE"}
        else 400
    )
    return ErrorResponse(
        error.code,
        "Report request could not be completed",
        request_id,
        status,
        error.retry_after_seconds,
    )
