from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest
from ansvis_adapter.application.ports import SourceAuthRequest
from ansvis_adapter.domain.auth import RegisteredSource
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.infrastructure.bearer_auth import (
    BearerAuthPolicy,
    HmacBearerSourceAuthenticator,
)

NOW = datetime(2030, 1, 1, tzinfo=UTC)
NOW_SECONDS = int(NOW.timestamp())
TEST_KEY = hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:ansvis-auth-key").digest()


def _segment(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def _raw_segment(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("ascii")).rstrip(b"=").decode("ascii")


def _signed_token(
    *,
    header: dict[str, object] | None = None,
    claims: dict[str, object] | None = None,
    key: bytes = TEST_KEY,
) -> str:
    token_header = header or {"alg": "HS256", "typ": "JWT", "kid": "ansvis_key_v1"}
    token_claims = claims or {
        "iss": "issuer_test_ansvis_0001",
        "aud": "camera-ai-ansvis-ingestion",
        "sub": "source_subject_test_0001",
        "iat": NOW_SECONDS - 30,
        "exp": NOW_SECONDS + 270,
        "jti": "jti_test_ansvis_0001",
    }
    signing_input = f"{_segment(token_header)}.{_segment(token_claims)}"
    signature = base64.urlsafe_b64encode(
        hmac.digest(key, signing_input.encode("ascii"), "sha256")
    ).rstrip(b"=")
    return f"{signing_input}.{signature.decode('ascii')}"


def _signed_raw_token(header: str, claims: str) -> str:
    signing_input = f"{_raw_segment(header)}.{_raw_segment(claims)}"
    signature = base64.urlsafe_b64encode(
        hmac.digest(TEST_KEY, signing_input.encode("ascii"), "sha256")
    ).rstrip(b"=")
    return f"{signing_input}.{signature.decode('ascii')}"


class FakeKeys:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def key_for(self, key_id: str) -> bytes | None:
        if self.fail:
            raise RuntimeError("synthetic key provider failure")
        return TEST_KEY if key_id == "ansvis_key_v1" else None


class FakeRevocations:
    def __init__(self, *, revoked: bool = False, fail: bool = False) -> None:
        self.revoked = revoked
        self.fail = fail

    def is_revoked(self, token_id: str) -> bool:
        assert token_id == "jti_test_ansvis_0001"
        if self.fail:
            raise RuntimeError("synthetic revocation provider failure")
        return self.revoked


class FakeSources:
    def __init__(
        self,
        *,
        source: RegisteredSource | None = None,
        missing: bool = False,
        fail: bool = False,
    ) -> None:
        self.source = (
            None
            if missing
            else source
            or RegisteredSource(
                subject_ref="source_subject_test_0001",
                source_namespace="ansvis.test.source",
                tenant_ref="tenant_test_0001",
                school_ref="school_test_0001",
                active=True,
            )
        )
        self.fail = fail

    def find_by_subject(self, subject_ref: str) -> RegisteredSource | None:
        assert subject_ref == "source_subject_test_0001"
        if self.fail:
            raise RuntimeError("synthetic source provider failure")
        return self.source


def authenticator(
    *,
    keys: FakeKeys | None = None,
    revocations: FakeRevocations | None = None,
    sources: FakeSources | None = None,
) -> HmacBearerSourceAuthenticator:
    return HmacBearerSourceAuthenticator(
        policy=BearerAuthPolicy(trusted_issuer="issuer_test_ansvis_0001"),
        keys=keys or FakeKeys(),
        revocations=revocations or FakeRevocations(),
        sources=sources or FakeSources(),
        now=lambda: NOW,
    )


def request_for(token: str, *, secure: bool = True) -> SourceAuthRequest:
    return SourceAuthRequest(
        declared_source_namespace="ansvis.test.source",
        authorization_values=(f"Bearer {token}",),
        transport_secure=secure,
    )


def test_valid_bearer_maps_to_authoritative_registered_source() -> None:
    source = authenticator().authenticate(request_for(_signed_token()))

    assert source.source_namespace == "ansvis.test.source"
    assert source.subject_ref == "source_subject_test_0001"
    assert source.tenant_ref == "tenant_test_0001"
    assert source.school_ref == "school_test_0001"


@pytest.mark.parametrize(
    ("authorization_values", "secure", "expected_code"),
    [
        ((), True, "EVENT_AUTH_TOKEN_INVALID"),
        (("Basic synthetic",), True, "EVENT_AUTH_TOKEN_INVALID"),
        (("Bearer malformed",), True, "EVENT_AUTH_TOKEN_INVALID"),
        (("Bearer one", "Bearer two"), True, "EVENT_AUTH_TOKEN_INVALID"),
        (
            (f"Bearer {_signed_token()}, Bearer {_signed_token()}",),
            True,
            "EVENT_AUTH_TOKEN_INVALID",
        ),
        ((f"bearer {_signed_token()}",), True, "EVENT_AUTH_TOKEN_INVALID"),
        (("Bearer synthetic",), False, "EVENT_SOURCE_UNAUTHORIZED"),
    ],
)
def test_transport_and_authorization_header_are_unambiguous(
    authorization_values: tuple[str, ...], secure: bool, expected_code: str
) -> None:
    request = SourceAuthRequest(
        declared_source_namespace="ansvis.test.source",
        authorization_values=authorization_values,
        transport_secure=secure,
    )

    with pytest.raises(AnsvisAdapterError) as raised:
        authenticator().authenticate(request)

    assert raised.value.code == expected_code


@pytest.mark.parametrize(
    "token",
    [
        _signed_token(header={"alg": "none", "typ": "JWT", "kid": "ansvis_key_v1"}),
        _signed_token(
            header={"alg": "HS256", "typ": "JWT", "kid": "ansvis_key_v1", "x": "blocked"}
        ),
        _signed_token(key=hashlib.sha256(b"SYNTHETIC_TEST_DATA_ONLY:other-key").digest()),
        _signed_token(header={"alg": "HS256", "typ": "JWT", "kid": "unknown_key"}),
        _signed_raw_token(
            '{"alg":"HS256","typ":"JWT","kid":"ansvis_key_v1","kid":"other_key"}',
            '{"iss":"issuer_test_ansvis_0001","aud":"camera-ai-ansvis-ingestion",'
            '"sub":"source_subject_test_0001","iat":1893455970,"exp":1893456270,'
            '"jti":"jti_test_ansvis_0001"}',
        ),
    ],
)
def test_algorithm_signature_key_and_duplicate_header_fail_closed(token: str) -> None:
    with pytest.raises(AnsvisAdapterError, match="EVENT_AUTH_TOKEN_INVALID"):
        authenticator().authenticate(request_for(token))


@pytest.mark.parametrize(
    "token",
    [
        _signed_raw_token(
            '{"alg":"HS256","typ":"JWT","kid":"ansvis_key_v1"',
            '{"iss":"issuer_test_ansvis_0001","aud":"camera-ai-ansvis-ingestion",'
            '"sub":"source_subject_test_0001","iat":1893455970,"exp":1893456270,'
            '"jti":"jti_test_ansvis_0001"}',
        ),
        _signed_raw_token(
            '{"alg":"HS256","typ":"JWT","kid":"ansvis_key_v1"}',
            '{"iss":"issuer_test_ansvis_0001","aud":"camera-ai-ansvis-ingestion",'
            '"sub":"source_subject_test_0001","iat":NaN,"exp":1893456270,'
            '"jti":"jti_test_ansvis_0001"}',
        ),
        _signed_raw_token(
            '["HS256","JWT","ansvis_key_v1"]',
            '{"iss":"issuer_test_ansvis_0001","aud":"camera-ai-ansvis-ingestion",'
            '"sub":"source_subject_test_0001","iat":1893455970,"exp":1893456270,'
            '"jti":"jti_test_ansvis_0001"}',
        ),
        _signed_raw_token(
            '{"alg":"HS256","typ":"JWT","kid":"ansvis_key_v1"}',
            '{"iss":"' + "x" * 2_100 + '"}',
        ),
        _signed_token(header={"alg": "HS256", "typ": "JWS", "kid": "ansvis_key_v1"}),
    ],
)
def test_malformed_non_finite_non_object_and_oversized_tokens_fail_closed(token: str) -> None:
    with pytest.raises(AnsvisAdapterError, match="EVENT_AUTH_TOKEN_INVALID"):
        authenticator().authenticate(request_for(token))


@pytest.mark.parametrize(
    "claim_changes",
    [
        {"iss": "issuer_test_other_0001"},
        {"aud": "camera-ai-other"},
        {"sub": "invalid subject"},
        {"jti": "invalid"},
        {"iat": NOW_SECONDS + 31},
        {"iat": NOW_SECONDS - 30, "exp": NOW_SECONDS + 271},
        {"iat": float(NOW_SECONDS)},
        {"iat": True},
        {"exp": 9_007_199_254_740_992},
        {"extra": "blocked"},
    ],
)
def test_invalid_claims_fail_closed(claim_changes: dict[str, object]) -> None:
    claims: dict[str, object] = {
        "iss": "issuer_test_ansvis_0001",
        "aud": "camera-ai-ansvis-ingestion",
        "sub": "source_subject_test_0001",
        "iat": NOW_SECONDS - 30,
        "exp": NOW_SECONDS + 270,
        "jti": "jti_test_ansvis_0001",
    }
    claims.update(claim_changes)

    with pytest.raises(AnsvisAdapterError, match="EVENT_AUTH_TOKEN_INVALID"):
        authenticator().authenticate(request_for(_signed_token(claims=claims)))


def test_expired_token_has_stable_masked_code() -> None:
    claims = {
        "iss": "issuer_test_ansvis_0001",
        "aud": "camera-ai-ansvis-ingestion",
        "sub": "source_subject_test_0001",
        "iat": NOW_SECONDS - 300,
        "exp": NOW_SECONDS,
        "jti": "jti_test_ansvis_0001",
    }

    with pytest.raises(AnsvisAdapterError) as raised:
        authenticator().authenticate(request_for(_signed_token(claims=claims)))

    assert raised.value.code == "EVENT_AUTH_TOKEN_EXPIRED"
    assert "issuer_test" not in str(raised.value)


@pytest.mark.parametrize(
    ("keys", "revocations", "expected_code"),
    [
        (FakeKeys(fail=True), FakeRevocations(), "EVENT_AUTH_TOKEN_INVALID"),
        (FakeKeys(), FakeRevocations(fail=True), "EVENT_AUTH_TOKEN_INVALID"),
        (FakeKeys(), FakeRevocations(revoked=True), "EVENT_AUTH_TOKEN_INVALID"),
    ],
)
def test_key_and_revocation_dependencies_fail_closed(
    keys: FakeKeys, revocations: FakeRevocations, expected_code: str
) -> None:
    with pytest.raises(AnsvisAdapterError) as raised:
        authenticator(keys=keys, revocations=revocations).authenticate(request_for(_signed_token()))
    assert raised.value.code == expected_code


def test_registered_source_must_be_active_and_match_declared_namespace() -> None:
    inactive = RegisteredSource(
        subject_ref="source_subject_test_0001",
        source_namespace="ansvis.test.source",
        tenant_ref="tenant_test_0001",
        school_ref="school_test_0001",
        active=False,
    )
    mismatch = RegisteredSource(
        subject_ref="source_subject_test_0001",
        source_namespace="ansvis.test.other",
        tenant_ref="tenant_test_0001",
        school_ref="school_test_0001",
        active=True,
    )
    subject_mismatch = RegisteredSource(
        subject_ref="source_subject_test_other_0001",
        source_namespace="ansvis.test.source",
        tenant_ref="tenant_test_0001",
        school_ref="school_test_0001",
        active=True,
    )

    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_MAPPING_DENIED"):
        authenticator(sources=FakeSources(missing=True)).authenticate(request_for(_signed_token()))
    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_MAPPING_DENIED"):
        authenticator(sources=FakeSources(source=inactive)).authenticate(
            request_for(_signed_token())
        )
    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_UNAUTHORIZED"):
        authenticator(sources=FakeSources(source=mismatch)).authenticate(
            request_for(_signed_token())
        )
    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_MAPPING_DENIED"):
        authenticator(sources=FakeSources(source=subject_mismatch)).authenticate(
            request_for(_signed_token())
        )
    with pytest.raises(AnsvisAdapterError, match="EVENT_SOURCE_MAPPING_DENIED"):
        authenticator(sources=FakeSources(fail=True)).authenticate(request_for(_signed_token()))


def test_duplicate_claim_is_rejected_without_retaining_marker() -> None:
    token = _signed_raw_token(
        '{"alg":"HS256","typ":"JWT","kid":"ansvis_key_v1"}',
        '{"iss":"issuer_test_ansvis_0001","iss":"blocked_test_marker",'
        '"aud":"camera-ai-ansvis-ingestion","sub":"source_subject_test_0001",'
        '"iat":1893455970,"exp":1893456270,"jti":"jti_test_ansvis_0001"}',
    )

    with pytest.raises(AnsvisAdapterError) as raised:
        authenticator().authenticate(request_for(token))

    assert raised.value.code == "EVENT_AUTH_TOKEN_INVALID"
    assert "blocked_test_marker" not in str(raised.value)
