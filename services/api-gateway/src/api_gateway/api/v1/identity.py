"""Gateway-only authentication ingress with allowlisted forwarding."""

from __future__ import annotations

import hashlib
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response

from api_gateway.api.errors import error_response, request_id_from
from api_gateway.application.identity import IdentityUpstream, IdentityUpstreamUnavailable

router = APIRouter(prefix="/auth", tags=["authentication"])
MAX_AUTH_BODY_BYTES = 8_192


def _upstream(request: Request) -> IdentityUpstream:
    upstream: object = getattr(request.app.state, "identity_upstream", None)
    if upstream is None or not hasattr(upstream, "forward"):
        raise IdentityUpstreamUnavailable
    return cast(IdentityUpstream, upstream)


def _source_key(request: Request) -> str:
    client = request.client
    if client is None:
        raise IdentityUpstreamUnavailable
    digest = hashlib.sha256(b"camera-ai|gateway-source-v1|" + client.host.encode()).hexdigest()
    return f"source.{digest}"


def _authorization(request: Request) -> str | None:
    values = request.headers.getlist("authorization")
    if len(values) > 1:
        raise ValueError
    return None if not values else values[0]


class InvalidAuthBody(ValueError):
    """Invalid size or framing without exposing request data."""


async def _bounded_body(request: Request) -> bytes:
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1:
        raise InvalidAuthBody
    declared: int | None = None
    if lengths:
        value = lengths[0]
        if not value.isascii() or not value.isdecimal() or len(value) > 10:
            raise InvalidAuthBody
        declared = int(value)
        if declared > MAX_AUTH_BODY_BYTES:
            raise InvalidAuthBody
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_AUTH_BODY_BYTES:
            raise InvalidAuthBody
        body.extend(chunk)
    if declared is not None and declared != len(body):
        raise InvalidAuthBody
    return bytes(body)


async def _forward(request: Request, path: str) -> Response:
    request_id = request_id_from(request)
    try:
        body = await _bounded_body(request)
        upstream_response = await _upstream(request).forward(
            path=path,
            body=body,
            authorization=_authorization(request),
            request_id=request_id,
            source_key=_source_key(request),
        )
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=dict(upstream_response.headers),
        )
    except InvalidAuthBody:
        return error_response(
            status_code=400,
            error_code="BAD_REQUEST",
            message="The request is invalid.",
            request_id=request_id,
        )
    except ValueError:
        return error_response(
            status_code=401,
            error_code="AUTHENTICATION_REQUIRED",
            message="Authentication is required.",
            request_id=request_id,
        )
    except IdentityUpstreamUnavailable:
        return error_response(
            status_code=503,
            error_code="AUTH_DEPENDENCY_UNAVAILABLE",
            message="Authentication is temporarily unavailable.",
            request_id=request_id,
        )


@router.post("/login")
async def login(request: Request) -> Response:
    return await _forward(request, "/api/v1/auth/login")


@router.post("/refresh")
async def refresh(request: Request) -> Response:
    return await _forward(request, "/api/v1/auth/refresh")


@router.post("/logout")
async def logout(request: Request) -> Response:
    return await _forward(request, "/api/v1/auth/logout")


@router.post("/session/snapshot")
async def session_snapshot(request: Request) -> Response:
    return await _forward(request, "/api/v1/auth/session/snapshot")


@router.post("/logout-all")
async def logout_all(request: Request) -> Response:
    return await _forward(request, "/api/v1/auth/logout-all")


@router.post("/mfa/enroll")
async def enroll_mfa(request: Request) -> Response:
    return await _forward(request, "/api/v1/auth/mfa/enroll")


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(session_id: UUID, request: Request) -> Response:
    return await _forward(request, f"/api/v1/auth/sessions/{session_id}/revoke")
