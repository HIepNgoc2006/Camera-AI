"""Strict ANSVIS Login Required Bearer/JWS source authenticator."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Never

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    RegisteredSourceRepository,
    SigningKeyProvider,
    SourceAuthenticator,
    SourceAuthRequest,
    TokenRevocationChecker,
)
from ansvis_adapter.domain.auth import STABLE_CODE_PATTERN, STABLE_REF_PATTERN
from ansvis_adapter.domain.errors import AnsvisAdapterError

AUTHORIZATION_PATTERN = re.compile(
    r"^Bearer (?P<token>[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$"
)
TOKEN_ID_PATTERN = re.compile(r"^jti_[A-Za-z0-9_-]{8,120}$")
MAX_TOKEN_LENGTH = 2_048
MAX_HEADER_BYTES = 512
MAX_CLAIMS_BYTES = 1_536
SAFE_INTEGER_MAX = 9_007_199_254_740_991
EXPECTED_HEADER_FIELDS = frozenset({"alg", "typ", "kid"})
EXPECTED_CLAIM_FIELDS = frozenset({"iss", "aud", "sub", "iat", "exp", "jti"})


def system_utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class BearerAuthPolicy:
    """Non-secret verification policy fixed by the V1 ANSVIS contract."""

    trusted_issuer: str
    audience: str = "camera-ai-ansvis-ingestion"
    max_token_lifetime_seconds: int = 300
    future_tolerance_seconds: int = 30

    def __post_init__(self) -> None:
        if (
            not 1 <= len(self.trusted_issuer) <= 256
            or not self.trusted_issuer.isprintable()
            or self.trusted_issuer.strip() != self.trusted_issuer
        ):
            raise ValueError("trusted issuer must be a printable exact identifier")
        if self.audience != "camera-ai-ansvis-ingestion":
            raise ValueError("audience must match the V1 ingestion audience")
        if self.max_token_lifetime_seconds != 300 or self.future_tolerance_seconds != 30:
            raise ValueError("Bearer timing must match the approved V1 policy")


def _reject_constant(_: str) -> Never:
    raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        result[key] = value
    return result


def _decode_segment(segment: str, *, max_bytes: int) -> bytes:
    if not segment or "=" in segment:
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
    try:
        decoded = base64.b64decode(
            segment + "=" * (-len(segment) % 4), altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError):
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID") from None
    if len(decoded) > max_bytes:
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    if not hmac.compare_digest(segment, canonical):
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
    return decoded


def _json_object(data: bytes) -> dict[str, object]:
    try:
        value: object = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID") from None
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
    return value


def _required_text(value: object, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or (pattern is not None and pattern.fullmatch(value) is None):
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
    return value


def _numeric_date(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= SAFE_INTEGER_MAX:
        raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
    return value


class HmacBearerSourceAuthenticator(SourceAuthenticator):
    """Verify a fixed HS256 profile and bind its subject to one registered source."""

    def __init__(
        self,
        *,
        policy: BearerAuthPolicy,
        keys: SigningKeyProvider,
        revocations: TokenRevocationChecker,
        sources: RegisteredSourceRepository,
        now: Callable[[], datetime] = system_utc_now,
    ) -> None:
        self._policy = policy
        self._keys = keys
        self._revocations = revocations
        self._sources = sources
        self._now = now

    def authenticate(self, request: SourceAuthRequest) -> AuthenticatedSource:
        if not request.transport_secure:
            raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")
        if len(request.authorization_values) != 1:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        authorization = request.authorization_values[0]
        if not 39 <= len(authorization) <= len("Bearer ") + MAX_TOKEN_LENGTH:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        matched = AUTHORIZATION_PATTERN.fullmatch(authorization)
        if matched is None:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        token = matched.group("token")
        if not 32 <= len(token) <= MAX_TOKEN_LENGTH:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")

        subject_ref = self._verify(token)
        try:
            registered = self._sources.find_by_subject(subject_ref)
        except Exception:
            raise AnsvisAdapterError("EVENT_SOURCE_MAPPING_DENIED") from None
        if registered is None or not registered.active or registered.subject_ref != subject_ref:
            raise AnsvisAdapterError("EVENT_SOURCE_MAPPING_DENIED")
        if registered.source_namespace != request.declared_source_namespace:
            raise AnsvisAdapterError("EVENT_SOURCE_UNAUTHORIZED")
        return AuthenticatedSource(
            source_namespace=registered.source_namespace,
            subject_ref=registered.subject_ref,
            tenant_ref=registered.tenant_ref,
            school_ref=registered.school_ref,
        )

    def _verify(self, token: str) -> str:
        header_segment, claims_segment, signature_segment = token.split(".")
        header = _json_object(_decode_segment(header_segment, max_bytes=MAX_HEADER_BYTES))
        claims_bytes = _decode_segment(claims_segment, max_bytes=MAX_CLAIMS_BYTES)
        signature = _decode_segment(signature_segment, max_bytes=hashlib.sha256().digest_size)
        if len(signature) != hashlib.sha256().digest_size:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        if set(header) != EXPECTED_HEADER_FIELDS:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        key_id = _required_text(header.get("kid"), STABLE_CODE_PATTERN)
        try:
            key = self._keys.key_for(key_id)
        except Exception:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID") from None
        if key is None or not isinstance(key, bytes) or not 32 <= len(key) <= 128:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        signing_input = f"{header_segment}.{claims_segment}".encode("ascii")
        expected_signature = hmac.digest(key, signing_input, "sha256")
        if not hmac.compare_digest(signature, expected_signature):
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")

        claims = _json_object(claims_bytes)
        if set(claims) != EXPECTED_CLAIM_FIELDS:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        if (
            claims.get("iss") != self._policy.trusted_issuer
            or claims.get("aud") != self._policy.audience
        ):
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        subject_ref = _required_text(claims.get("sub"), STABLE_REF_PATTERN)
        token_id = _required_text(claims.get("jti"), TOKEN_ID_PATTERN)
        issued_at = _numeric_date(claims.get("iat"))
        expires_at = _numeric_date(claims.get("exp"))
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
        received_at = int(now.astimezone(UTC).timestamp())
        if expires_at <= received_at:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_EXPIRED")
        if (
            issued_at > received_at + self._policy.future_tolerance_seconds
            or expires_at <= issued_at
            or expires_at - issued_at > self._policy.max_token_lifetime_seconds
        ):
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        try:
            revoked = self._revocations.is_revoked(token_id)
        except Exception:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID") from None
        if revoked:
            raise AnsvisAdapterError("EVENT_AUTH_TOKEN_INVALID")
        return subject_ref
