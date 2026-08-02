from __future__ import annotations

from api_gateway.config import Settings
from api_gateway.main import create_app


def test_openapi_exposes_health_and_identity_ingress_contracts() -> None:
    schema = create_app(Settings(environment="test", log_level="CRITICAL")).openapi()

    assert schema["info"]["title"] == "Camera AI API Gateway"
    assert set(schema["paths"]) == {
        "/healthz",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
        "/api/v1/auth/session/snapshot",
        "/api/v1/auth/mfa/enroll",
        "/api/v1/auth/sessions/{session_id}/revoke",
    }

    health_operation = schema["paths"]["/healthz"]["get"]
    assert health_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }
    assert health_operation["responses"]["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
