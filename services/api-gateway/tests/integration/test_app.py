from __future__ import annotations

import re

from api_gateway.api.request_id import REQUEST_ID_PATTERN
from api_gateway.config import Settings
from api_gateway.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_health_response_is_minimal_and_correlated() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/healthz", headers={"X-Request-ID": "req-health-123"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "request_id": "req-health-123"}
    assert response.headers["X-Request-ID"] == "req-health-123"


def test_health_generates_request_id_when_header_is_missing() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/healthz")

    request_id = response.json()["request_id"]
    assert REQUEST_ID_PATTERN.fullmatch(request_id) is not None
    assert response.headers["X-Request-ID"] == request_id


def test_oversized_request_id_is_not_reflected() -> None:
    oversized = "x" * 65
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/healthz", headers={"X-Request-ID": oversized})

    replacement = response.headers["X-Request-ID"]
    assert replacement != oversized
    assert REQUEST_ID_PATTERN.fullmatch(replacement) is not None


def test_not_found_uses_stable_error_shape_and_correlation() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/does-not-exist", headers={"X-Request-ID": "req-not-found"})

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "RESOURCE_NOT_FOUND",
        "message": "Resource not found",
        "request_id": "req-not-found",
    }
    assert response.headers["X-Request-ID"] == "req-not-found"


def test_unexpected_error_hides_exception_details_and_keeps_correlation() -> None:
    application = create_app(Settings(environment="test", log_level="CRITICAL"))

    @application.get("/__test__/failure", include_in_schema=False)
    async def fail_for_test() -> None:
        raise RuntimeError("fake-sensitive-exception-marker")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get(
            "/__test__/failure",
            headers={"X-Request-ID": "req-failure"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "INTERNAL_SERVER_ERROR",
        "message": "An internal error occurred",
        "request_id": "req-failure",
    }
    assert response.headers["X-Request-ID"] == "req-failure"
    assert re.search("sensitive|RuntimeError", response.text, re.IGNORECASE) is None


def test_production_disables_interactive_api_documentation() -> None:
    application: FastAPI = create_app(Settings(environment="production", log_level="CRITICAL"))

    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None
