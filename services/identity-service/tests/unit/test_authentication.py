from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pyotp
import pytest
from camera_ai_audit import AuditIntent, IntentResult
from camera_ai_crypto import DeterministicFakeKeyProvider, EncryptionService
from fastapi.testclient import TestClient
from identity_service.application.authentication import AuthenticationService, TokenPair
from identity_service.application.errors import AuthenticationError
from identity_service.config import Settings
from identity_service.domain.auth import LoginSubject, MfaFactor, MfaState
from identity_service.domain.models import UserStatus
from identity_service.infrastructure.memory import (
    InMemoryAuthRepository,
    InMemoryLoginRateLimiter,
    UnavailableLoginRateLimiter,
)
from identity_service.infrastructure.security import (
    Argon2idPasswordVerifier,
    Encv1MfaProtector,
    JwtAccessTokenCodec,
    LoginLookupHasher,
    PyotpTotpVerifier,
)
from identity_service.main import create_app

NOW = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
TENANT = UUID("00000000-0000-4000-8000-000000000101")
OTHER_TENANT = UUID("00000000-0000-4000-8000-000000000102")
SCHOOL = UUID("00000000-0000-4000-8000-000000000201")
USER = UUID("00000000-0000-4000-8000-000000000301")
REQUEST_ID = "req_synthetic_auth_0001"
IDENTIFIER = "synthetic.user@example.invalid"
PASSWORD = "SYNTHETIC-FAKE-PASSWORD-ONLY"
SOURCE = "source.synthetic.0001"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def _build(
    *,
    roles: frozenset[str] = frozenset({"teacher"}),
    limiter: InMemoryLoginRateLimiter | UnavailableLoginRateLimiter | None = None,
) -> tuple[
    AuthenticationService,
    InMemoryAuthRepository,
    LoginLookupHasher,
    Argon2idPasswordVerifier,
    Encv1MfaProtector,
]:
    repository = InMemoryAuthRepository()
    lookup = LoginLookupHasher(b"l" * 32)
    passwords = Argon2idPasswordVerifier()
    protector = Encv1MfaProtector(EncryptionService(DeterministicFakeKeyProvider(seed=b"k" * 32)))
    repository.seed_subject(
        tenant_id=TENANT,
        login_digest=lookup.digest(IDENTIFIER, tenant_id=TENANT),
        subject=LoginSubject(
            user_id=USER,
            tenant_id=TENANT,
            school_id=SCHOOL,
            status=UserStatus.ACTIVE,
            password_hash=passwords.hash(PASSWORD),
            role_codes=roles,
        ),
    )
    service = AuthenticationService(
        repository=repository,
        limiter=limiter or InMemoryLoginRateLimiter(),
        lookup=lookup,
        passwords=passwords,
        tokens=JwtAccessTokenCodec(
            signing_key=b"t" * 32,
            key_id="synthetic_key_0001",
            issuer="identity.synthetic.0001",
        ),
        mfa=protector,
        totp=PyotpTotpVerifier(),
    )
    return service, repository, lookup, passwords, protector


def _login(service: AuthenticationService, **changes: object) -> TokenPair:
    values: dict[str, object] = {
        "tenant_id": TENANT,
        "identifier": IDENTIFIER,
        "password": PASSWORD,
        "source_key": SOURCE,
        "request_id": REQUEST_ID,
        "now": NOW,
    }
    values.update(changes)
    return service.login(**values)  # type: ignore[arg-type]


def test_unknown_user_and_wrong_password_are_identical_stable_failures() -> None:
    service, repository, _, _, _ = _build()
    observed: list[tuple[str, str]] = []
    for identifier, password in (
        ("unknown@example.invalid", PASSWORD),
        (IDENTIFIER, "SYNTHETIC-WRONG-PASSWORD"),
    ):
        with pytest.raises(AuthenticationError) as raised:
            _login(service, identifier=identifier, password=password)
        observed.append((raised.value.code, str(raised.value)))
    assert observed == [
        ("AUTH_CREDENTIAL_INVALID", "AUTH_CREDENTIAL_INVALID"),
        ("AUTH_CREDENTIAL_INVALID", "AUTH_CREDENTIAL_INVALID"),
    ]
    assert {intent.action for intent in repository.audit_intents} == {"AUTH_LOGIN_FAILED"}
    payloads = repr([intent.publisher_payload() for intent in repository.audit_intents])
    assert PASSWORD not in payloads
    assert "WRONG-PASSWORD" not in payloads


def test_unknown_user_and_wrong_password_have_byte_identical_http_responses() -> None:
    service, _, _, _, _ = _build()
    application = create_app(
        Settings(environment="test", log_level="CRITICAL"),
        authentication_service=service,
    )
    bodies: list[bytes] = []
    with TestClient(application) as client:
        for identifier, password in (
            ("unknown@example.invalid", PASSWORD),
            (IDENTIFIER, "SYNTHETIC-WRONG-PASSWORD"),
        ):
            response = client.post(
                "/api/v1/auth/login",
                headers={
                    "X-Request-ID": REQUEST_ID,
                    "X-Client-Source": SOURCE,
                },
                json={
                    "tenant_id": str(TENANT),
                    "identifier": identifier,
                    "password": password,
                },
            )
            assert response.status_code == 401
            bodies.append(response.content)
    assert bodies[0] == bodies[1]


def test_refresh_rotation_and_replay_revoke_entire_family() -> None:
    service, repository, _, _, _ = _build()
    initial = _login(service)
    rotated = service.refresh(
        refresh_token=initial.refresh_token,
        request_id=REQUEST_ID,
        now=NOW + timedelta(minutes=1),
    )
    service.verify_access(rotated.access_token, now=NOW + timedelta(minutes=1))

    with pytest.raises(AuthenticationError, match="AUTH_REFRESH_REUSE_DETECTED"):
        service.refresh(
            refresh_token=initial.refresh_token,
            request_id=REQUEST_ID,
            now=NOW + timedelta(minutes=2),
        )
    with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
        service.verify_access(rotated.access_token, now=NOW + timedelta(minutes=2))
    assert "SESSION_REVOKED" in {intent.action for intent in repository.audit_intents}


def test_logout_all_revokes_access_and_refresh() -> None:
    service, _, _, _, _ = _build()
    first = _login(service)
    second = _login(service, source_key="source.synthetic.0002")
    assert service.logout_all(first.access_token, request_id=REQUEST_ID, now=NOW) == 2
    for token in (first.access_token, second.access_token):
        with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
            service.verify_access(token, now=NOW)
    with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
        service.refresh(refresh_token=second.refresh_token, request_id=REQUEST_ID, now=NOW)


def test_admin_requires_totp_and_secret_only_round_trips_through_encv1() -> None:
    service, repository, _, _, protector = _build(roles=frozenset({"admin"}))
    factor_id = UUID("00000000-0000-4000-8000-000000000401")
    factor = MfaFactor(
        factor_id=factor_id,
        user_id=USER,
        tenant_id=TENANT,
        secret_ciphertext=protector.protect(
            factor_id=factor_id,
            tenant_id=TENANT,
            secret=TOTP_SECRET,
        ),
        state=MfaState.ACTIVE,
        created_at=NOW - timedelta(days=1),
        verified_at=NOW - timedelta(days=1),
    )
    repository.save_mfa_factor(
        factor=factor,
        audit=repository.audit_intents[0] if repository.audit_intents else _audit_placeholder(),
    )
    with pytest.raises(AuthenticationError, match="AUTH_MFA_REQUIRED"):
        _login(service)

    code = pyotp.TOTP(TOTP_SECRET).at(NOW)
    pair = _login(service, mfa_code=code, source_key="source.synthetic.0002")
    assert pair.mfa_verified is True
    second = _login(service, mfa_code=code, source_key="source.synthetic.0003")
    assert service.administrative_revoke(
        pair.access_token,
        session_id=second.session_id,
        request_id=REQUEST_ID,
        now=NOW,
    )
    service.verify_access(pair.access_token, now=NOW)
    with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
        service.verify_access(second.access_token, now=NOW)
    assert factor.secret_ciphertext.startswith(b"ENCV1")
    combined = repr(pair) + repr([audit.publisher_payload() for audit in repository.audit_intents])
    assert TOTP_SECRET not in combined
    assert code not in combined


def test_rate_limit_boundary_and_dependency_loss_fail_closed() -> None:
    limiter = InMemoryLoginRateLimiter(account_limit=1, source_limit=10)
    service, _, _, _, _ = _build(limiter=limiter)
    with pytest.raises(AuthenticationError, match="AUTH_CREDENTIAL_INVALID"):
        _login(service, password="SYNTHETIC-WRONG-PASSWORD")
    with pytest.raises(AuthenticationError) as limited:
        _login(service)
    assert limited.value.code == "AUTH_RATE_LIMITED"
    assert limited.value.retry_after is not None

    unavailable, _, _, _, _ = _build(limiter=UnavailableLoginRateLimiter())
    with pytest.raises(AuthenticationError, match="AUTH_RATE_LIMIT_UNAVAILABLE"):
        _login(unavailable)


def test_source_rate_limit_cannot_be_bypassed_with_a_different_account() -> None:
    limiter = InMemoryLoginRateLimiter(account_limit=10, source_limit=1)
    service, _, _, _, _ = _build(limiter=limiter)
    with pytest.raises(AuthenticationError, match="AUTH_CREDENTIAL_INVALID"):
        _login(service, identifier="unknown@example.invalid")
    with pytest.raises(AuthenticationError, match="AUTH_RATE_LIMITED"):
        _login(service)
    _login(service, source_key="source.synthetic.0002")


def test_access_token_rejects_cross_tenant_expiry_revocation_and_clock_skew() -> None:
    service, _, _, _, _ = _build()
    pair = _login(service)
    with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
        service.verify_access(pair.access_token, expected_tenant_id=OTHER_TENANT, now=NOW)
    service.verify_access(pair.access_token, now=NOW + timedelta(minutes=5, seconds=29))
    with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
        service.verify_access(pair.access_token, now=NOW + timedelta(minutes=5, seconds=31))
    service.logout(pair.access_token, request_id=REQUEST_ID, now=NOW)
    with pytest.raises(AuthenticationError, match="AUTHENTICATION_REQUIRED"):
        service.verify_access(pair.access_token, now=NOW)


def _audit_placeholder() -> AuditIntent:
    return AuditIntent(
        source_service="identity-service",
        source_event_id=UUID("00000000-0000-4000-8000-000000000501"),
        action="MFA_CHANGED",
        resource_type="mfa_factor",
        request_id=REQUEST_ID,
        result=IntentResult.SUCCESS,
        occurred_at=NOW,
        resource_id=UUID("00000000-0000-4000-8000-000000000401"),
    )
