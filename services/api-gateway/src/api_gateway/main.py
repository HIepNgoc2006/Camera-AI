"""FastAPI application factory for the Camera AI API Gateway."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api_gateway.api.errors import http_exception_handler, validation_exception_handler
from api_gateway.api.health import router as health_router
from api_gateway.api.middleware import RequestContextMiddleware
from api_gateway.api.v1.router import router as api_v1_router
from api_gateway.application.identity import IdentityUpstream
from api_gateway.config import Settings, load_settings
from api_gateway.logging import configure_logging


def create_app(
    settings: Settings | None = None,
    *,
    identity_upstream: IdentityUpstream | None = None,
) -> FastAPI:
    """Create the gateway with safe defaults and no external dependencies."""

    runtime_settings = load_settings() if settings is None else settings
    production = runtime_settings.environment == "production"
    application = FastAPI(
        title="Camera AI API Gateway",
        version="0.1.0",
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    application.state.settings = runtime_settings
    application.state.identity_upstream = identity_upstream
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
