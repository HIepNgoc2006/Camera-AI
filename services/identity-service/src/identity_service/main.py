"""FastAPI application factory for the internal Identity Service."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from identity_service.api.errors import http_exception_handler, validation_exception_handler
from identity_service.api.health import router as health_router
from identity_service.api.middleware import RequestContextMiddleware
from identity_service.api.v1.router import router as api_v1_router
from identity_service.application.authentication import AuthenticationService
from identity_service.config import Settings, load_settings
from identity_service.logging import configure_logging


def create_app(
    settings: Settings | None = None,
    *,
    authentication_service: AuthenticationService | None = None,
) -> FastAPI:
    runtime_settings = load_settings() if settings is None else settings
    production = runtime_settings.environment == "production"
    application = FastAPI(
        title="Camera AI Identity Service",
        version="0.1.0",
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    application.state.settings = runtime_settings
    application.state.authentication_service = authentication_service
    application.add_middleware(
        RequestContextMiddleware,
        settings=runtime_settings,
        logger=configure_logging(runtime_settings),
    )
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.include_router(health_router)
    application.include_router(api_v1_router)
    return application


app = create_app()
