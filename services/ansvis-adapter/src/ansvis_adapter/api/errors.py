"""Stable public errors with no reflected payload or exception detail."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ansvis_adapter.api.request_id import generated_request_id
from ansvis_adapter.schemas.responses import ErrorResponse

ERROR_STATUS = {
    "EVENT_AUTH_TOKEN_EXPIRED": 401,
    "EVENT_AUTH_TOKEN_INVALID": 401,
    "EVENT_BODY_TOO_LARGE": 413,
    "EVENT_CONSENT_UNAVAILABLE": 503,
    "EVENT_CONTENT_TYPE_UNSUPPORTED": 415,
    "EVENT_DURABLE_RECEIPT_UNAVAILABLE": 503,
    "EVENT_FALLBACK_IDENTITY_INSUFFICIENT": 422,
    "EVENT_IDEMPOTENCY_CONFLICT": 409,
    "EVENT_SCHEMA_INVALID": 422,
    "EVENT_SOURCE_UNAUTHORIZED": 401,
    "EVENT_SOURCE_MAPPING_DENIED": 401,
    "EVENT_TYPE_UNSUPPORTED": 422,
    "TIME_EVENT_FUTURE": 409,
    "TIME_FRACTION_PRECISION": 422,
    "TIME_REPLAY_WINDOW_EXCEEDED": 409,
    "TIME_SOURCE_UNHEALTHY": 503,
    "TIME_TIMESTAMP_INVALID": 422,
    "TIME_TIMESTAMP_NAIVE": 422,
}


def request_id_from(request: Request) -> str:
    value: object = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else generated_request_id()


def error_response(*, status_code: int, error_code: str, request_id: str) -> JSONResponse:
    body = ErrorResponse(
        error_code=error_code,
        message="Request rejected.",
        request_id=request_id,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def adapter_error_response(request: Request, error_code: str) -> JSONResponse:
    status_code = ERROR_STATUS.get(error_code, 500)
    public_code = error_code if error_code in ERROR_STATUS else "INTERNAL_SERVER_ERROR"
    request.state.error_code = public_code
    return error_response(
        status_code=status_code,
        error_code=public_code,
        request_id=request_id_from(request),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return error_response(
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            request_id=request_id_from(request),
        )
    if exc.status_code == 404:
        return error_response(
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            request_id=request_id_from(request),
        )
    if exc.status_code == 405:
        return error_response(
            status_code=405,
            error_code="METHOD_NOT_ALLOWED",
            request_id=request_id_from(request),
        )
    return error_response(
        status_code=exc.status_code,
        error_code="HTTP_ERROR",
        request_id=request_id_from(request),
    )


async def validation_exception_handler(request: Request, _: Exception) -> JSONResponse:
    return error_response(
        status_code=422,
        error_code="EVENT_SCHEMA_INVALID",
        request_id=request_id_from(request),
    )
