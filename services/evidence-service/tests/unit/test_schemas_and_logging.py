from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest
from evidence_service.api.errors import to_error_response
from evidence_service.domain.errors import EvidenceError
from evidence_service.logging import safe_log
from evidence_service.schemas.commands import AccessRequestV1, UploadRequestV1
from pydantic import ValidationError


def test_upload_schema_rejects_binary_and_unknown_actor_scope_fields() -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "source_event_id": UUID("00000000-0000-4000-8000-000000006731"),
        "camera_id": None,
        "task_id": None,
        "captured_at": datetime(2026, 7, 28, tzinfo=UTC),
        "media_kind": "image",
        "content_type": "image/png",
        "original_extension": "png",
        "declared_size_bytes": 1024,
        "sensitivity": "critical",
        "retention_policy_version": "attendance_retention_v1",
        "retention_days": 30,
        "retention_expires_at": datetime(2026, 8, 28, tzinfo=UTC),
    }
    assert UploadRequestV1.model_validate(payload).declared_size_bytes == 1024
    for forbidden in ("image_base64", "signed_url", "actor_id", "tenant_id", "school_id"):
        with pytest.raises(ValidationError):
            UploadRequestV1.model_validate({**payload, forbidden: "synthetic"})


def test_access_schema_keeps_actions_separate_and_rejects_oversized_ttl() -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "evidence_id": UUID("00000000-0000-4000-8000-000000006732"),
        "action": "view_thumbnail",
        "ttl_seconds": 60,
        "consent_state": "allowed",
        "reason_code": None,
    }
    assert AccessRequestV1.model_validate(payload).command().action.value == "view_thumbnail"
    with pytest.raises(ValidationError):
        AccessRequestV1.model_validate({**payload, "ttl_seconds": 301})
    with pytest.raises(ValidationError):
        AccessRequestV1.model_validate({**payload, "action": "view_and_download"})


def test_logging_drops_urls_locators_hashes_and_personal_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("evidence-test")
    with caplog.at_level(logging.INFO, logger=logger.name):
        safe_log(
            logger,
            logging.INFO,
            {
                "request_id": "req_673333333333",
                "state": "available",
                "signed_url": "https://private.invalid/secret",
                "object_key": "evidence/v1/secret",
                "sha256": "a" * 64,
                "student_name": "synthetic-forbidden",
            },
        )
    payload = json.loads(caplog.messages[-1])
    assert payload == {
        "request_id": "req_673333333333",
        "service_name": "evidence-storage-service",
        "state": "available",
    }


def test_public_errors_conceal_internal_authorization_and_storage_details() -> None:
    concealed = to_error_response(
        EvidenceError("EVIDENCE_AUTHORITY_DENIED"),
        "req_674444444444",
    )
    unavailable = to_error_response(
        EvidenceError("EVIDENCE_DATABASE_UNAVAILABLE"),
        "req_674444444445",
    )
    assert concealed.error_code == "EVIDENCE_NOT_FOUND"
    assert concealed.request_id == "req_674444444444"
    assert unavailable.error_code == "EVIDENCE_ACCESS_UNAVAILABLE"
