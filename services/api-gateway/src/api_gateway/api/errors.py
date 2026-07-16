"""Map framework errors to the stable public error envelope."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api_gateway.api.request_id import generated_request_id
from api_gateway.schemas import ErrorResponse


def request_id_from(request: Request) -> str:
    """Return middleware correlation state, with a defensive fallback."""

    request_id: object = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else generated_request_id()


def error_response(
    *, status_code: int, error_code: str, message: str, request_id: str
) -> JSONResponse:
    """Build a JSON error response from explicit safe fields."""

    body = ErrorResponse(error_code=error_code, message=message, request_id=request_id)
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return stable messages without reflecting arbitrary exception details."""

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
    """Hide validation internals behind a stable public message."""

    return error_response(
        status_code=422,
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed",
        request_id=request_id_from(request),
    )
