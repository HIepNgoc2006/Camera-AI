from __future__ import annotations

from api_gateway.config import Settings
from api_gateway.main import create_app


def test_openapi_exposes_only_the_process_health_contract() -> None:
    schema = create_app(Settings(environment="test", log_level="CRITICAL")).openapi()

    assert schema["info"]["title"] == "Camera AI API Gateway"
    assert set(schema["paths"]) == {"/healthz"}

    health_operation = schema["paths"]["/healthz"]["get"]
    assert health_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }
    assert health_operation["responses"]["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
