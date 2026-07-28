from __future__ import annotations

import json
from pathlib import Path

from ansvis_adapter.config import Settings
from ansvis_adapter.domain.models import HealthStatusEvent
from ansvis_adapter.main import create_app
from ansvis_adapter.schemas.events import parse_and_normalize_event

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_openapi_exposes_only_liveness_and_ansvis_ingestion() -> None:
    schema = create_app(Settings(environment="test", log_level="CRITICAL")).openapi()

    assert schema["info"]["title"] == "Camera AI ANSVIS Adapter"
    assert set(schema["paths"]) == {"/healthz", "/integration/ansvis/events"}
    operation = schema["paths"]["/integration/ansvis/events"]["post"]
    assert operation["responses"]["202"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/IngestionAck"
    }
    for status in ("200", "401", "409", "413", "415", "422", "429", "503"):
        assert status in operation["responses"]


def test_public_response_models_are_strict_and_minimal() -> None:
    schema = create_app(Settings(environment="test", log_level="CRITICAL")).openapi()
    components = schema["components"]["schemas"]

    assert components["ErrorResponse"]["additionalProperties"] is False
    assert set(components["ErrorResponse"]["properties"]) == {
        "error_code",
        "message",
        "request_id",
    }
    assert components["IngestionAck"]["additionalProperties"] is False
    assert set(components["IngestionAck"]["properties"]) == {
        "schema_version",
        "outcome",
        "receipt_id",
        "request_id",
        "correlation_id",
    }


def test_parser_consumes_the_versioned_synthetic_contract_fixture() -> None:
    fixture_path = (
        REPOSITORY_ROOT / "packages" / "test-fixtures" / "ansvis" / "event.synthetic.json"
    )
    document: object = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    assert document.get("_fixture") == "SYNTHETIC_TEST_DATA_ONLY"
    request = document.get("request")
    assert isinstance(request, dict)

    event = parse_and_normalize_event(request)

    assert isinstance(event, HealthStatusEvent)
    assert event.source_namespace == "ansvis.test.source"
    assert event.source_event_id == "event_test_ansvis_0001"
