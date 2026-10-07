from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from api_gateway.application.identity import IdentityUpstreamResponse
from api_gateway.config import Settings as GatewaySettings
from api_gateway.infrastructure.identity import HttpxIdentityUpstream
from api_gateway.main import create_app as create_gateway
from camera_ai_crypto import DeterministicFakeKeyProvider, EncryptionService
from fastapi.testclient import TestClient
from identity_service.application.authentication import AuthenticationService
from identity_service.application.errors import AuthenticationError
from identity_service.config import Settings as IdentitySettings
from identity_service.domain.auth import LoginSubject
from identity_service.domain.models import UserStatus
from identity_service.infrastructure.memory import (
    InMemoryAuthRepository,
    InMemoryLoginRateLimiter,
)
from identity_service.infrastructure.security import (
    Argon2idPasswordVerifier,
    Encv1MfaProtector,
    JwtAccessTokenCodec,
    LoginLookupHasher,
    PyotpTotpVerifier,
)
from identity_service.main import create_app as create_identity
from starlette.types import Message, Scope

TENANT = UUID("00000000-0000-4000-8000-000000000101")
SCHOOL = UUID("00000000-0000-4000-8000-000000000201")
USER = UUID("00000000-0000-4000-8000-000000000301")
IDENTIFIER = "synthetic.gateway.user@example.invalid"
PASSWORD = "SYNTHETIC-FAKE-PASSWORD-ONLY"
REQUEST_ID = "req_gateway_auth_0001"


def _applications() -> tuple[TestClient, AuthenticationService]:
    repository = InMemoryAuthRepository()
    lookup = LoginLookupHasher(b"l" * 32)
    passwords = Argon2idPasswordVerifier()
    repository.seed_subject(
        tenant_id=TENANT,
        login_digest=lookup.digest(IDENTIFIER, tenant_id=TENANT),
        subject=LoginSubject(
            user_id=USER,
            tenant_id=TENANT,
            school_id=SCHOOL,
            status=UserStatus.ACTIVE,
            password_hash=passwords.hash(PASSWORD),
            role_codes=frozenset({"teacher"}),
        ),
    )
    service = AuthenticationService(
        repository=repository,
        limiter=InMemoryLoginRateLimiter(),
        lookup=lookup,
        passwords=passwords,
        tokens=JwtAccessTokenCodec(
            signing_key=b"t" * 32,
            key_id="synthetic_key_0001",
            issuer="identity.synthetic.0001",
        ),
        mfa=Encv1MfaProtector(EncryptionService(DeterministicFakeKeyProvider(seed=b"k" * 32))),
        totp=PyotpTotpVerifier(),
    )
    identity_app = create_identity(
        IdentitySettings(environment="test", log_level="CRITICAL"),
        authentication_service=service,
    )
    upstream = HttpxIdentityUpstream(
        base_url="http://127.0.0.1",
        transport=httpx.ASGITransport(app=identity_app),
    )
    gateway = create_gateway(
        GatewaySettings(environment="test", log_level="CRITICAL"),
        identity_upstream=upstream,
    )
    return TestClient(gateway), service


def test_client_logs_in_refreshes_and_logs_out_only_through_gateway() -> None:
    client, service = _applications()
    with client:
        login = client.post(
            "/api/v1/auth/login",
            headers={
                "X-Request-ID": REQUEST_ID,
                "X-Client-Source": "untrusted.client.value",
            },
            json={
                "tenant_id": str(TENANT),
                "identifier": IDENTIFIER,
                "password": PASSWORD,
            },
        )
        assert login.status_code == 200
        pair = login.json()
        snapshot = client.post(
            "/api/v1/auth/session/snapshot",
            headers={
                "X-Request-ID": REQUEST_ID,
                "Authorization": f"Bearer {pair['access_token']}",
            },
        )
        assert snapshot.status_code == 200
        assert snapshot.json()["policyVersion"] == "identity_session_snapshot_v1"
        assert pair["access_token"] not in snapshot.text
        assert pair["refresh_token"] not in snapshot.text
        refreshed = client.post(
            "/api/v1/auth/refresh",
            headers={"X-Request-ID": REQUEST_ID},
            json={"refresh_token": pair["refresh_token"]},
        )
        assert refreshed.status_code == 200
        rotated = refreshed.json()
        logout = client.post(
            "/api/v1/auth/logout",
            headers={
                "X-Request-ID": REQUEST_ID,
                "Authorization": f"Bearer {rotated['access_token']}",
            },
        )
        assert logout.status_code == 200
    with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
        service.verify_access(rotated["access_token"], now=datetime.now(UTC))


def test_gateway_preserves_enumeration_safe_identity_response() -> None:
    client, _ = _applications()
    responses: list[bytes] = []
    with client:
        for identifier, password in (
            ("unknown@example.invalid", PASSWORD),
            (IDENTIFIER, "SYNTHETIC-WRONG-PASSWORD"),
        ):
            response = client.post(
                "/api/v1/auth/login",
                headers={"X-Request-ID": REQUEST_ID},
                json={
                    "tenant_id": str(TENANT),
                    "identifier": identifier,
                    "password": password,
                },
            )
            assert response.status_code == 401
            responses.append(response.content)
    assert responses[0] == responses[1]


def test_gateway_fails_closed_without_identity_upstream() -> None:
    gateway = create_gateway(GatewaySettings(environment="test", log_level="CRITICAL"))
    with TestClient(gateway) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"X-Request-ID": REQUEST_ID},
            json={
                "tenant_id": str(TENANT),
                "identifier": IDENTIFIER,
                "password": PASSWORD,
            },
        )
    assert response.status_code == 503
    assert response.json()["error_code"] == "AUTH_DEPENDENCY_UNAVAILABLE"


@pytest.mark.parametrize(
    "declared_length,expected_reads",
    [
        (None, 9),
        ("12288", 0),
        ("-1", 0),
        ("invalid", 0),
        ("8192,8192", 0),
    ],
)
def test_gateway_bounds_stream_before_buffering_or_forwarding(
    declared_length: str | None,
    expected_reads: int,
) -> None:
    gateway = create_gateway(GatewaySettings(environment="test", log_level="CRITICAL"))
    reads = 0
    messages: list[Message] = []

    async def receive() -> Message:
        nonlocal reads
        reads += 1
        return {"type": "http.request", "body": b"x" * 1024, "more_body": reads < 12}

    async def send(message: Message) -> None:
        messages.append(message)

    headers = [(b"x-request-id", REQUEST_ID.encode())]
    if declared_length is not None:
        headers.append((b"content-length", declared_length.encode()))
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "raw_path": b"/api/v1/auth/login",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 80),
    }
    asyncio.run(gateway(scope, receive, send))
    assert messages[0]["status"] == 400
    assert reads == expected_reads
    assert b'"BAD_REQUEST"' in b"".join(m.get("body", b"") for m in messages)


def test_gateway_exact_body_limit_forwarding_and_invalid_framing() -> None:
    received: list[bytes] = []

    class Upstream:
        async def forward(self, **kwargs: object) -> IdentityUpstreamResponse:
            body = kwargs["body"]
            assert isinstance(body, bytes)
            received.append(body)
            return IdentityUpstreamResponse(status_code=200, content=b"{}")

    gateway = create_gateway(
        GatewaySettings(environment="test", log_level="CRITICAL"), identity_upstream=Upstream()
    )
    with TestClient(gateway) as client:
        payload = b"x" * 8192
        assert client.post("/api/v1/auth/login", content=payload).status_code == 200
        assert received == [payload]
        for headers in (
            [("Content-Length", "2"), ("Content-Length", "2")],
            [("Content-Length", "1")],
            [("Content-Length", "3")],
        ):
            response = client.post("/api/v1/auth/login", content=b"{}", headers=headers)
            assert response.status_code == 400
            assert response.json()["error_code"] == "BAD_REQUEST"
        assert received == [payload]
