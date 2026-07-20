"""FastAPI application factory for the fail-closed ANSVIS adapter."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ansvis_adapter.api.errors import http_exception_handler, validation_exception_handler
from ansvis_adapter.api.events import create_event_router
from ansvis_adapter.api.health import router as health_router
from ansvis_adapter.api.middleware import RequestContextMiddleware
from ansvis_adapter.application.ports import DurableReceiptPort, SourceAuthenticator
from ansvis_adapter.application.service import IngestAnsvisEvent, system_utc_now
from ansvis_adapter.config import Settings, load_settings
from ansvis_adapter.infrastructure.unavailable import (
    UnavailableDurableReceiptPort,
    UnavailableSourceAuthenticator,
)
from ansvis_adapter.logging import configure_logging


def create_app(
    settings: Settings | None = None,
    *,
    authenticator: SourceAuthenticator | None = None,
    receipt_port: DurableReceiptPort | None = None,
    request_logger: logging.Logger | None = None,
    now: Callable[[], datetime] = system_utc_now,
) -> FastAPI:
    runtime_settings = load_settings() if settings is None else settings
    production = runtime_settings.environment == "production"
    application = FastAPI(
        title="Camera AI ANSVIS Adapter",
        version="0.1.0",
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    service = IngestAnsvisEvent(
        authenticator or UnavailableSourceAuthenticator(),
        receipt_port or UnavailableDurableReceiptPort(),
        now=now,
    )
    application.add_middleware(
        RequestContextMiddleware,
        settings=runtime_settings,
        logger=(configure_logging(runtime_settings) if request_logger is None else request_logger),
    )
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.include_router(health_router)
    application.include_router(create_event_router(service))
    return application


app = create_app()
