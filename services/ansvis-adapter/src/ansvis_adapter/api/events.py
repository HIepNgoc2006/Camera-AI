"""Bounded JSON endpoint for the ANSVIS HTTP Trigger contract."""

from __future__ import annotations

import contextlib
import re
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from camera_ai_audit import AuditIntent, AuditIntentRecorder, IntentResult
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ansvis_adapter.api.errors import adapter_error_response, request_id_from
from ansvis_adapter.application.ports import MetricsSink, ReceiptOutcome, SourceRateLimiter
from ansvis_adapter.application.service import IngestAnsvisEvent
from ansvis_adapter.application.telemetry import NullMetricsSink
from ansvis_adapter.config import MAX_EVENT_BODY_BYTES
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.schemas.events import inspect_json_envelope, load_json_object
from ansvis_adapter.schemas.responses import ErrorResponse, IngestionAck

AUDIT_SOURCE_SERVICE = "ansvis-adapter-service"
SOURCE_AUTH_DENIAL_CODES = frozenset(
    {
        "EVENT_AUTH_TOKEN_EXPIRED",
        "EVENT_AUTH_TOKEN_INVALID",
        "EVENT_SOURCE_MAPPING_DENIED",
        "EVENT_SOURCE_UNAUTHORIZED",
    }
)
_AUDIT_REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
REJECTION_REASON_BY_CODE = {
    "EVENT_AUTH_TOKEN_EXPIRED": "authentication",
    "EVENT_AUTH_TOKEN_INVALID": "authentication",
    "EVENT_BODY_TOO_LARGE": "body_size",
    "EVENT_CONTENT_TYPE_UNSUPPORTED": "content_type",
    "EVENT_FALLBACK_IDENTITY_INSUFFICIENT": "malformed",
    "EVENT_IDEMPOTENCY_CONFLICT": "replay",
    "EVENT_RATE_LIMITED": "rate_limited",
    "EVENT_RATE_LIMIT_UNAVAILABLE": "rate_limit_unavailable",
    "EVENT_SCHEMA_INVALID": "malformed",
    "EVENT_SOURCE_MAPPING_DENIED": "source_mapping",
    "EVENT_SOURCE_UNAUTHORIZED": "authentication",
    "EVENT_TYPE_UNSUPPORTED": "malformed",
    "TIME_EVENT_FUTURE": "replay",
    "TIME_FRACTION_PRECISION": "replay",
    "TIME_REPLAY_WINDOW_EXCEEDED": "replay",
    "TIME_SOURCE_UNHEALTHY": "replay",
    "TIME_TIMESTAMP_INVALID": "replay",
    "TIME_TIMESTAMP_NAIVE": "replay",
}


def _rejected_metric(metrics: MetricsSink) -> None:
    try:
        metrics.increment("event_ingestion_total", outcome="rejected")
    except Exception:
        return


def _rejection_reason_metric(metrics: MetricsSink, error_code: str) -> None:
    reason = REJECTION_REASON_BY_CODE.get(error_code)
    if reason is None:
        return
    try:
        metrics.increment("event_ingestion_rejections_total", outcome=reason)
    except Exception:
        return


def _ack_duration_metric(metrics: MetricsSink, started_at: float) -> None:
    try:
        metrics.observe("event_ingestion_ack_seconds", seconds=perf_counter() - started_at)
    except Exception:
        return


def _audit_request_id(candidate: str) -> str:
    return candidate if _AUDIT_REQUEST_ID.fullmatch(candidate) else f"req_{uuid4().hex}"


def _record_auth_denial(
    audit: AuditIntentRecorder | None, *, reason_code: str, request_id: str
) -> None:
    """Best-effort denial evidence: the request is already denied fail-closed, so a broken
    audit path must not turn a 401 into an availability incident; recorder failures are
    swallowed here and surface through the audit-outbox backlog gauge instead."""

    if audit is None:
        return
    with contextlib.suppress(Exception):
        audit.record(
            AuditIntent(
                source_service=AUDIT_SOURCE_SERVICE,
                source_event_id=uuid4(),
                action="ANSVIS_SOURCE_AUTH_DENIED",
                resource_type="ansvis_source",
                request_id=_audit_request_id(request_id),
                result=IntentResult.DENIED,
                reason_code=reason_code,
                occurred_at=datetime.now(UTC),
            )
        )


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
        if declared_length < 0:
            raise AnsvisAdapterError("EVENT_SCHEMA_INVALID")
        if declared_length > MAX_EVENT_BODY_BYTES:
            raise AnsvisAdapterError("EVENT_BODY_TOO_LARGE")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_EVENT_BODY_BYTES:
            raise AnsvisAdapterError("EVENT_BODY_TOO_LARGE")
    return bytes(body)


def create_event_router(
    service: IngestAnsvisEvent,
    rate_limiter: SourceRateLimiter,
    *,
    metrics: MetricsSink | None = None,
    audit: AuditIntentRecorder | None = None,
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
            429: {"model": ErrorResponse, "description": "Source rate limit exceeded"},
            503: {"model": ErrorResponse, "description": "Idempotency or receipt unavailable"},
        },
        summary="Receive one normalized ANSVIS event",
    )
    async def ingest_event(request: Request) -> JSONResponse:
        started_at = perf_counter()
        dispatched = False
        retry_after: int | None = None
        try:
            received_at = service.capture_trusted_receipt_time()
            if request.url.scheme != "https":
                raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")
            body = await _bounded_json_body(request)
            source_namespace = inspect_json_envelope(body)
            rate_decision = rate_limiter.check(source_namespace)
            if not rate_decision.allowed:
                retry_after = rate_decision.retry_after_seconds
                raise AnsvisAdapterError("EVENT_RATE_LIMITED")
            source = service.authenticate_source(
                source_namespace,
                authorization_values=tuple(request.headers.getlist("authorization")),
                transport_secure=True,
            )
            payload = load_json_object(body)
            dispatched = True
            receipt = service.execute_authenticated(
                payload,
                source,
                received_at=received_at,
            )
        except AnsvisAdapterError as exc:
            if not dispatched:
                _rejected_metric(runtime_metrics)
            _rejection_reason_metric(runtime_metrics, exc.code)
            if exc.code in SOURCE_AUTH_DENIAL_CODES:
                _record_auth_denial(
                    audit, reason_code=exc.code, request_id=request_id_from(request)
                )
            _ack_duration_metric(runtime_metrics, started_at)
            headers = (
                {"Retry-After": str(max(1, retry_after))}
                if exc.code == "EVENT_RATE_LIMITED" and retry_after is not None
                else None
            )
            return adapter_error_response(request, exc.code, headers=headers)

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
        _ack_duration_metric(runtime_metrics, started_at)
        return JSONResponse(status_code=status_code, content=ack.model_dump())

    return router
