"""Bounded JSON endpoint for the ANSVIS HTTP Trigger contract."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ansvis_adapter.api.errors import adapter_error_response, request_id_from
from ansvis_adapter.application.ports import MetricsSink, ReceiptOutcome
from ansvis_adapter.application.service import IngestAnsvisEvent
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.config import MAX_EVENT_BODY_BYTES
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.schemas.events import load_json_object
from ansvis_adapter.schemas.responses import ErrorResponse, IngestionAck


def _rejected_metric(metrics: MetricsSink) -> None:
    try:
        metrics.increment("event_ingestion_total", outcome="rejected")
    except Exception:
        return


async def _bounded_json_body(request: Request) -> bytes:
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip().lower()
    if content_type != "application/json":
        raise AnsvisAdapterError("EVENT_CONTENT_TYPE_UNSUPPORTED")
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            raise AnsvisAdapterError("EVENT_SCHEMA_INVALID") from None
        if declared_length > MAX_EVENT_BODY_BYTES:
            raise AnsvisAdapterError("EVENT_BODY_TOO_LARGE")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_EVENT_BODY_BYTES:
            raise AnsvisAdapterError("EVENT_BODY_TOO_LARGE")
    return bytes(body)


def create_event_router(
    service: IngestAnsvisEvent, *, metrics: MetricsSink | None = None
) -> APIRouter:
    router = APIRouter(tags=["ansvis-integration"])
    runtime_metrics = metrics or NullMetricsSink()

    @router.post(
        "/integration/ansvis/events",
        response_model=IngestionAck,
        status_code=202,
        responses={
            200: {"model": IngestionAck, "description": "Committed duplicate receipt"},
            401: {"model": ErrorResponse, "description": "Source not authenticated"},
            409: {"model": ErrorResponse, "description": "Replay or receipt conflict"},
            413: {"model": ErrorResponse, "description": "Body exceeds 64 KiB"},
            415: {"model": ErrorResponse, "description": "JSON content type required"},
            422: {"model": ErrorResponse, "description": "Event contract rejected"},
            503: {"model": ErrorResponse, "description": "Idempotency or receipt unavailable"},
        },
        summary="Receive one normalized ANSVIS event",
    )
    async def ingest_event(request: Request) -> JSONResponse:
        dispatched = False
        try:
            payload = load_json_object(await _bounded_json_body(request))
            dispatched = True
            receipt = service.execute(
                payload,
                authorization_values=tuple(request.headers.getlist("authorization")),
                transport_secure=request.url.scheme == "https",
            )
        except AnsvisAdapterError as exc:
            if not dispatched:
                _rejected_metric(runtime_metrics)
            return adapter_error_response(request, exc.code)

        correlation_id = payload.get("correlation_id")
        if not isinstance(correlation_id, str):
            return adapter_error_response(request, "EVENT_SCHEMA_INVALID")
        ack = IngestionAck(
            outcome=receipt.outcome.value,
            receipt_id=receipt.receipt_id,
            request_id=request_id_from(request),
            correlation_id=correlation_id,
        )
        status_code = 202 if receipt.outcome is ReceiptOutcome.ACCEPTED else 200
        return JSONResponse(status_code=status_code, content=ack.model_dump())

    return router
