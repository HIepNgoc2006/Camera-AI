"""Map framework errors to the stable public error envelope."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from identity_service.api.request_id import generated_request_id
from identity_service.schemas import ErrorResponse

ERRORS: dict[str, tuple[int, str]] = {
    "AUTH_CREDENTIAL_INVALID": (401, "Authentication failed."),
    "AUTH_MFA_REQUIRED": (401, "Additional authentication is required."),
    "AUTH_MFA_VERIFICATION_FAILED": (401, "Additional authentication failed."),
    "AUTH_REFRESH_REUSE_DETECTED": (401, "Authentication is required."),
    "AUTHENTICATION_REQUIRED": (401, "Authentication is required."),
    "AUTH_SOURCE_CONTEXT_REQUIRED": (400, "Trusted request context is required."),
    "AUTH_RATE_LIMITED": (429, "Too many authentication attempts."),
    "AUTH_RATE_LIMIT_UNAVAILABLE": (503, "Authentication is temporarily unavailable."),
    "AUTH_DEPENDENCY_UNAVAILABLE": (503, "Authentication is temporarily unavailable."),
    "AUTHZ_DENIED": (404, "The requested resource is unavailable."),
}


def request_id_from(request: Request) -> str:
    request_id: object = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else generated_request_id()


def error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error_code=error_code, message=message, request_id=request_id)
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def authentication_error_response(
    *, code: str, request_id: str, retry_after: int | None = None
) -> JSONResponse:
    status_code, message = ERRORS.get(code, (503, "Authentication is temporarily unavailable."))
    headers = None if retry_after is None else {"Retry-After": str(max(1, retry_after))}
    return error_response(
        status_code=status_code,
        error_code=code,
        message=message,
        request_id=request_id,
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return error_response(
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            message="An internal error occurred",
            request_id=request_id_from(request),
        )
    if exc.status_code == 404:
        return error_response(
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            message="Resource not found",
            request_id=request_id_from(request),
        )
    if exc.status_code == 405:
        return error_response(
            status_code=405,
            error_code="METHOD_NOT_ALLOWED",
            message="Method not allowed",
            request_id=request_id_from(request),
        )
    return error_response(
        status_code=exc.status_code,
        error_code="HTTP_ERROR",
        message="Request could not be completed",
        request_id=request_id_from(request),
    )


async def validation_exception_handler(request: Request, _: Exception) -> JSONResponse:
    return error_response(
        status_code=422,
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed",
        request_id=request_id_from(request),
    )
