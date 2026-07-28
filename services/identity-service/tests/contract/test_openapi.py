from __future__ import annotations

from identity_service.config import Settings
from identity_service.main import create_app


def test_openapi_exposes_approved_authentication_surface() -> None:
    schema = create_app(Settings(environment="test", log_level="CRITICAL")).openapi()

    assert schema["info"]["title"] == "Camera AI Identity Service"
    assert set(schema["paths"]) == {
        "/healthz",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
        "/api/v1/auth/mfa/enroll",
        "/api/v1/auth/sessions/{session_id}/revoke",
    }
    assert schema["paths"]["/healthz"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/HealthResponse"}
