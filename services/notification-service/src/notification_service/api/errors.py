"""Stable internal error response mapping."""

from __future__ import annotations

from dataclasses import dataclass

from notification_service.domain.errors import NotificationError


@dataclass(frozen=True, slots=True)
class ErrorResponse:
    error_code: str
    message: str
    request_id: str


_PUBLIC = {
    "NOTIFICATION_NOT_AVAILABLE",
    "NOTIFICATION_REQUEST_INVALID",
    "NOTIFICATION_DELIVERY_UNAVAILABLE",
}


def to_error_response(error: NotificationError, request_id: str) -> ErrorResponse:
    code = error.code if error.code in _PUBLIC else "NOTIFICATION_NOT_AVAILABLE"
    message = {
        "NOTIFICATION_NOT_AVAILABLE": "Notification is not available.",
        "NOTIFICATION_REQUEST_INVALID": "Notification request is invalid.",
        "NOTIFICATION_DELIVERY_UNAVAILABLE": "Notification delivery is unavailable.",
    }[code]
    return ErrorResponse(error_code=code, message=message, request_id=request_id)
