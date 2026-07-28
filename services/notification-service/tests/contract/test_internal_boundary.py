from __future__ import annotations

from dataclasses import asdict

from notification_service.api.errors import to_error_response
from notification_service.domain.errors import NotificationError


def test_internal_errors_conceal_protected_object_and_dependency_details() -> None:
    for internal in (
        "NOTIFICATION_RECIPIENT_SCOPE_DENIED",
        "NOTIFICATION_CONSENT_DENIED",
        "NOTIFICATION_ENDPOINT_DENIED",
        "NOTIFICATION_POLICY_INACTIVE",
        "NOTIFICATION_NOT_FOUND",
    ):
        response = to_error_response(
            NotificationError(internal),
            "req_synthetic_0001",
        )
        assert response.error_code == "NOTIFICATION_NOT_AVAILABLE"
        assert internal not in response.message
        assert response.request_id == "req_synthetic_0001"


def test_public_error_shape_is_stable() -> None:
    response = to_error_response(
        NotificationError("NOTIFICATION_REQUEST_INVALID"),
        "req_synthetic_0001",
    )
    assert set(asdict(response)) == {"error_code", "message", "request_id"}
