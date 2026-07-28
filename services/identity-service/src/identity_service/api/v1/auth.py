"""Versioned authentication routes for gateway-mediated calls."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from identity_service.api.errors import authentication_error_response, request_id_from
from identity_service.application.authentication import AuthenticationService, TokenPair
from identity_service.application.errors import AuthenticationError
from identity_service.infrastructure.security import validate_source_key
from identity_service.schemas import (
    LoginRequest,
    MfaEnrollRequest,
    OperationResponse,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _service(request: Request) -> AuthenticationService:
    service = getattr(request.app.state, "authentication_service", None)
    if not isinstance(service, AuthenticationService):
        raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE")
    return service


def _bearer(request: Request) -> str:
    values = request.headers.getlist("authorization")
    if len(values) != 1 or not values[0].startswith("Bearer "):
        raise AuthenticationError("AUTHENTICATION_REQUIRED")
    token = values[0][7:]
    if not token or "," in token or any(char.isspace() for char in token):
        raise AuthenticationError("AUTHENTICATION_REQUIRED")
    return token


def _token_response(pair: TokenPair, request_id: str) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type="Bearer",
        expires_in=pair.expires_in,
        session_id=pair.session_id,
        mfa_verified=pair.mfa_verified,
        request_id=request_id,
    )


def _source_key(request: Request) -> str:
    value = request.headers.get("X-Client-Source")
    if value is None:
        raise AuthenticationError("AUTH_SOURCE_CONTEXT_REQUIRED")
    return validate_source_key(value)


def _error(error: AuthenticationError, request_id: str) -> JSONResponse:
    return authentication_error_response(
        code=error.code,
        request_id=request_id,
        retry_after=error.retry_after,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse | JSONResponse:
    request_id = request_id_from(request)
    try:
        return _token_response(
            _service(request).login(
                tenant_id=payload.tenant_id,
                identifier=payload.identifier,
                password=payload.password,
                mfa_code=payload.mfa_code,
                source_key=_source_key(request),
                request_id=request_id,
            ),
            request_id,
        )
    except AuthenticationError as error:
        return _error(error, request_id)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request) -> TokenResponse | JSONResponse:
    request_id = request_id_from(request)
    try:
        return _token_response(
            _service(request).refresh(
                refresh_token=payload.refresh_token,
                request_id=request_id,
            ),
            request_id,
        )
    except AuthenticationError as error:
        return _error(error, request_id)


@router.post("/logout", response_model=OperationResponse)
def logout(request: Request) -> OperationResponse | JSONResponse:
    request_id = request_id_from(request)
    try:
        _service(request).logout(_bearer(request), request_id=request_id)
        return OperationResponse(operation="logout", request_id=request_id)
    except AuthenticationError as error:
        return _error(error, request_id)


@router.post("/logout-all", response_model=OperationResponse)
def logout_all(request: Request) -> OperationResponse | JSONResponse:
    request_id = request_id_from(request)
    try:
        affected = _service(request).logout_all(_bearer(request), request_id=request_id)
        return OperationResponse(
            operation="logout_all",
            affected_sessions=affected,
            request_id=request_id,
        )
    except AuthenticationError as error:
        return _error(error, request_id)


@router.post("/mfa/enroll", response_model=OperationResponse)
def enroll_mfa(payload: MfaEnrollRequest, request: Request) -> OperationResponse | JSONResponse:
    request_id = request_id_from(request)
    try:
        factor_id = _service(request).enroll_mfa(
            _bearer(request),
            secret=payload.secret,
            code=payload.code,
            request_id=request_id,
        )
        return OperationResponse(
            operation="mfa_enrolled",
            factor_id=factor_id,
            request_id=request_id,
        )
    except AuthenticationError as error:
        return _error(error, request_id)


@router.post("/sessions/{session_id}/revoke", response_model=OperationResponse)
def revoke_session(session_id: UUID, request: Request) -> OperationResponse | JSONResponse:
    request_id = request_id_from(request)
    try:
        found = _service(request).administrative_revoke(
            _bearer(request),
            session_id=session_id,
            request_id=request_id,
        )
        if not found:
            raise AuthenticationError("AUTHZ_DENIED")
        return OperationResponse(operation="session_revoked", request_id=request_id)
    except AuthenticationError as error:
        return _error(error, request_id)
