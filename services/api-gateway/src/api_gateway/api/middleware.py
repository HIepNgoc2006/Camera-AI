"""Gateway-wide request correlation and safe failure handling."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from api_gateway.api.errors import error_response
from api_gateway.api.request_id import REQUEST_ID_HEADER, select_request_id
from api_gateway.config import Settings
from api_gateway.logging import log_event


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Set correlation state, sanitize failures, and emit metadata-only logs."""

    def __init__(self, app: ASGIApp, *, settings: Settings, logger: logging.Logger) -> None:
        super().__init__(app)
        self._settings = settings
        self._logger = logger

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = select_request_id(request.headers.getlist(REQUEST_ID_HEADER))
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            response = error_response(
                status_code=500,
                error_code="INTERNAL_SERVER_ERROR",
                message="An internal error occurred",
                request_id=request_id,
            )
            log_event(
                self._logger,
                level=logging.ERROR,
                environment=self._settings.environment,
                event="request_failed",
                request_id=request_id,
                status_code=500,
                error_code="INTERNAL_SERVER_ERROR",
                exception_type=type(exc).__name__,
            )
        else:
            log_event(
                self._logger,
                level=logging.INFO,
                environment=self._settings.environment,
                event="request_completed",
                request_id=request_id,
                status_code=response.status_code,
            )

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
