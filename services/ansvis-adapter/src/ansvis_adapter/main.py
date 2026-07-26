"""FastAPI application factory for the fail-closed ANSVIS adapter."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime

from camera_ai_metrics import PrometheusMetricsSink, start_internal_metrics_server
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ansvis_adapter.api.errors import http_exception_handler, validation_exception_handler
from ansvis_adapter.api.events import create_event_router
from ansvis_adapter.api.health import router as health_router
from ansvis_adapter.api.middleware import RequestContextMiddleware
from ansvis_adapter.application.ports import (
    DurableReceiptPort,
    IdempotencyDeriver,
    MetricsSink,
    SourceAuthenticator,
)
from ansvis_adapter.application.service import IngestAnsvisEvent, system_utc_now
from ansvis_adapter.config import Settings, load_settings
from ansvis_adapter.infrastructure.unavailable import (
    UnavailableDurableReceiptPort,
    UnavailableIdempotencyDeriver,
    UnavailableSourceAuthenticator,
)
from ansvis_adapter.logging import configure_logging


def create_app(
    settings: Settings | None = None,
    *,
    authenticator: SourceAuthenticator | None = None,
    idempotency_deriver: IdempotencyDeriver | None = None,
    receipt_port: DurableReceiptPort | None = None,
    metrics: MetricsSink | None = None,
    request_logger: logging.Logger | None = None,
    now: Callable[[], datetime] = system_utc_now,
) -> FastAPI:
    runtime_settings = load_settings() if settings is None else settings
    if metrics is None:
        # Runnable default: registry-backed Prometheus sink. Tests inject NullMetricsSink.
        runtime_metrics: MetricsSink = PrometheusMetricsSink()
    else:
        runtime_metrics = metrics
    production = runtime_settings.environment == "production"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        server = None
        if runtime_settings.metrics_port != 0 and isinstance(
            runtime_metrics, PrometheusMetricsSink
        ):
            server = start_internal_metrics_server(
                runtime_metrics, port=runtime_settings.metrics_port
            )
        try:
            yield
        finally:
            if server is not None:
                server.shutdown()

    application = FastAPI(
        title="Camera AI ANSVIS Adapter",
        version="0.1.0",
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )
    service = IngestAnsvisEvent(
        authenticator or UnavailableSourceAuthenticator(),
        idempotency_deriver or UnavailableIdempotencyDeriver(),
        receipt_port or UnavailableDurableReceiptPort(),
        metrics=runtime_metrics,
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
    application.include_router(create_event_router(service, metrics=runtime_metrics))
    return application


app = create_app()
