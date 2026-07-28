from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
from identity_service.api.request_id import REQUEST_ID_PATTERN
from identity_service.config import Settings
from identity_service.main import create_app


def test_health_response_is_minimal_and_correlated() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/healthz", headers={"X-Request-ID": "req-identity-health"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "request_id": "req-identity-health"}
    assert response.headers["X-Request-ID"] == "req-identity-health"


def test_health_generates_request_id_when_missing() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/healthz")

    request_id = response.json()["request_id"]
    assert REQUEST_ID_PATTERN.fullmatch(request_id) is not None
    assert response.headers["X-Request-ID"] == request_id


def test_not_found_uses_stable_error_shape() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.get("/missing", headers={"X-Request-ID": "req-identity-missing"})

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "RESOURCE_NOT_FOUND",
        "message": "Resource not found",
        "request_id": "req-identity-missing",
    }


def test_unexpected_error_hides_exception_detail() -> None:
    application = create_app(Settings(environment="test", log_level="CRITICAL"))

    @application.get("/__test__/failure", include_in_schema=False)
    async def fail_for_test() -> None:
        raise RuntimeError("fake-sensitive-identity-marker")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get(
            "/__test__/failure",
            headers={"X-Request-ID": "req-identity-failure"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error_code": "INTERNAL_SERVER_ERROR",
        "message": "An internal error occurred",
        "request_id": "req-identity-failure",
    }
    assert re.search("sensitive|RuntimeError", response.text, re.IGNORECASE) is None


def test_production_disables_interactive_documentation() -> None:
    application: FastAPI = create_app(Settings(environment="production", log_level="CRITICAL"))
    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None


def test_authentication_runtime_is_fail_closed_when_not_composed() -> None:
    with TestClient(create_app(Settings(environment="test", log_level="CRITICAL"))) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={
                "X-Request-ID": "req-identity-unavailable",
                "X-Client-Source": "source.synthetic.0001",
            },
            json={
                "tenant_id": "00000000-0000-4000-8000-000000000101",
                "identifier": "synthetic.user@example.invalid",
                "password": "SYNTHETIC-FAKE-PASSWORD-ONLY",
            },
        )
    assert response.status_code == 503
    assert response.json() == {
        "error_code": "AUTH_DEPENDENCY_UNAVAILABLE",
        "message": "Authentication is temporarily unavailable.",
        "request_id": "req-identity-unavailable",
    }
