from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    DurableReceipt,
    ReceiptOutcome,
)
from ansvis_adapter.config import Settings
from ansvis_adapter.domain.auth import RegisteredSource
from ansvis_adapter.domain.models import NormalizedAnsvisEvent
from ansvis_adapter.infrastructure.bearer_auth import (
    BearerAuthPolicy,
    HmacBearerSourceAuthenticator,
)
from ansvis_adapter.main import create_app
from fastapi.testclient import TestClient

NOW = datetime(2030, 1, 1, tzinfo=UTC)
NOW_SECONDS = int(NOW.timestamp())
TEST_KEY = hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:route-auth-key").digest()


def event_payload() -> dict[str, object]:
    return {
        "schema_version": "ansvis_http_trigger_v1",
        "source_namespace": "ansvis.test.source",
        "source_event_id": "event_test_ansvis_auth_0001",
        "event_type": "camera.health.changed",
        "tenant_ref": "tenant_test_0001",
        "school_ref": "school_test_0001",
        "camera_external_id": "camera_test_0001",
        "task_external_id": "task_test_0001",
        "event_time": "2030-01-01T00:00:00Z",
        "correlation_id": "corr_test_ansvis_auth_0001",
        "attributes": {"status": "online"},
    }


def _segment(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def token(*, key: bytes = TEST_KEY, exp: int = NOW_SECONDS + 270) -> str:
    header = _segment({"alg": "HS256", "typ": "JWT", "kid": "ansvis_key_v1"})
    claims = _segment(
        {
            "iss": "issuer_test_ansvis_0001",
            "aud": "camera-ai-ansvis-ingestion",
            "sub": "source_subject_test_0001",
            "iat": NOW_SECONDS - 30,
            "exp": exp,
            "jti": "jti_test_ansvis_0001",
        }
    )
    signing_input = f"{header}.{claims}"
    signature = base64.urlsafe_b64encode(
        hmac.digest(key, signing_input.encode("ascii"), "sha256")
    ).rstrip(b"=")
    return f"{signing_input}.{signature.decode('ascii')}"


class FakeKeys:
    def key_for(self, key_id: str) -> bytes | None:
        return TEST_KEY if key_id == "ansvis_key_v1" else None


class FakeRevocations:
    def is_revoked(self, token_id: str) -> bool:
        return False


class FakeSources:
    def find_by_subject(self, subject_ref: str) -> RegisteredSource | None:
        return RegisteredSource(
            subject_ref=subject_ref,
            source_namespace="ansvis.test.source",
            tenant_ref="tenant_test_0001",
            school_ref="school_test_0001",
            active=True,
        )


class CommittedReceiptPort:
    def record(self, event: NormalizedAnsvisEvent, source: AuthenticatedSource) -> DurableReceipt:
        assert event.tenant_ref == source.tenant_ref
        return DurableReceipt(
            receipt_id="receipt_test_ansvis_auth_0001",
            outcome=ReceiptOutcome.ACCEPTED,
            commit_confirmed=True,
        )


def app_authenticator() -> HmacBearerSourceAuthenticator:
    return HmacBearerSourceAuthenticator(
        policy=BearerAuthPolicy(trusted_issuer="issuer_test_ansvis_0001"),
        keys=FakeKeys(),
        revocations=FakeRevocations(),
        sources=FakeSources(),
        now=lambda: NOW,
    )


def test_valid_bearer_reaches_only_the_committed_test_receipt() -> None:
    application = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=app_authenticator(),
        receipt_port=CommittedReceiptPort(),
        now=lambda: NOW,
    )
    with TestClient(application, base_url="https://testserver") as client:
        response = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers={"Authorization": f"Bearer {token()}"},
        )

    assert response.status_code == 202
    assert response.json()["outcome"] == "accepted"
    assert response.json()["receipt_id"] == "receipt_test_ansvis_auth_0001"


def test_invalid_signature_is_masked_in_response_and_logs(capsys: object) -> None:
    application = create_app(
        Settings(environment="test", log_level="INFO"),
        authenticator=app_authenticator(),
        receipt_port=CommittedReceiptPort(),
        now=lambda: NOW,
    )
    invalid_key = hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:invalid-route-key").digest()
    invalid_token = token(key=invalid_key)
    payload = event_payload()
    payload["attributes"] = {"status": "online", "raw_test_marker": "blocked_payload_marker"}
    with TestClient(application, base_url="https://testserver") as client:
        response = client.post(
            "/integration/ansvis/events",
            json=payload,
            headers={
                "Authorization": f"Bearer {invalid_token}",
                "X-Request-ID": "req-test-auth-invalid",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "EVENT_AUTH_TOKEN_INVALID",
        "message": "Request rejected.",
        "request_id": "req-test-auth-invalid",
    }
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    combined = captured.out + captured.err
    assert "EVENT_AUTH_TOKEN_INVALID" in combined
    assert invalid_token not in response.text
    assert invalid_token not in combined
    for marker in (
        invalid_key.hex(),
        "issuer_test_ansvis_0001",
        "source_subject_test_0001",
        "jti_test_ansvis_0001",
        "blocked_payload_marker",
    ):
        assert marker not in response.text
        assert marker not in combined
    assert "receipt_id" not in response.text


def test_expired_missing_and_insecure_bearer_requests_are_rejected() -> None:
    application = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=app_authenticator(),
        receipt_port=CommittedReceiptPort(),
        now=lambda: NOW,
    )
    with TestClient(application, base_url="https://testserver") as client:
        expired = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers={"Authorization": f"Bearer {token(exp=NOW_SECONDS)}"},
        )
        missing = client.post("/integration/ansvis/events", json=event_payload())
    with TestClient(application, base_url="http://testserver") as client:
        insecure = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers={"Authorization": f"Bearer {token()}"},
        )

    assert expired.status_code == 401
    assert expired.json()["error_code"] == "EVENT_AUTH_TOKEN_EXPIRED"
    assert missing.status_code == 401
    assert missing.json()["error_code"] == "EVENT_AUTH_TOKEN_INVALID"
    assert insecure.status_code == 401
    assert insecure.json()["error_code"] == "EVENT_SOURCE_UNAUTHORIZED"


def test_duplicate_and_combined_authorization_values_are_rejected() -> None:
    application = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=app_authenticator(),
        receipt_port=CommittedReceiptPort(),
        now=lambda: NOW,
    )
    bearer = f"Bearer {token()}"
    with TestClient(application, base_url="https://testserver") as client:
        duplicate = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers=[("Authorization", bearer), ("Authorization", bearer)],
        )
        combined = client.post(
            "/integration/ansvis/events",
            json=event_payload(),
            headers={"Authorization": f"{bearer}, {bearer}"},
        )

    assert duplicate.status_code == 401
    assert duplicate.json()["error_code"] == "EVENT_AUTH_TOKEN_INVALID"
    assert combined.status_code == 401
    assert combined.json()["error_code"] == "EVENT_AUTH_TOKEN_INVALID"
    assert "receipt_id" not in duplicate.text
    assert "receipt_id" not in combined.text


def test_verified_source_cannot_cross_tenant_boundary() -> None:
    application = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authenticator=app_authenticator(),
        receipt_port=CommittedReceiptPort(),
        now=lambda: NOW,
    )
    payload = event_payload()
    payload["tenant_ref"] = "tenant_test_other_0001"
    with TestClient(application, base_url="https://testserver") as client:
        response = client.post(
            "/integration/ansvis/events",
            json=payload,
            headers={"Authorization": f"Bearer {token()}"},
        )

    assert response.status_code == 401
    assert response.json()["error_code"] == "EVENT_SOURCE_MAPPING_DENIED"
    assert "receipt_id" not in response.text
