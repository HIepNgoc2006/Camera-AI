from __future__ import annotations

from identity_service.config import Settings
from identity_service.main import create_app


def test_openapi_exposes_health_only() -> None:
    schema = create_app(Settings(environment="test", log_level="CRITICAL")).openapi()

    assert schema["info"]["title"] == "Camera AI Identity Service"
    assert set(schema["paths"]) == {"/healthz"}
    assert schema["paths"]["/healthz"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/HealthResponse"}
