"""Approved credential, token, lookup and MFA adapters."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from camera_ai_crypto import EncryptionService, FieldBinding

from identity_service.application.errors import AuthenticationError
from identity_service.domain.auth import MfaFactor, SessionRecord

_TOKEN_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{10,512}\.[A-Za-z0-9_-]{10,4096}\.[A-Za-z0-9_-]{10,512}$"
)
_SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class LoginLookupHasher:
    """Purpose-bound HMAC lookup for normalized login identifiers."""

    key: bytes

    def __post_init__(self) -> None:
        if len(self.key) < 32:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE")

    def digest(self, identifier: str, *, tenant_id: UUID) -> bytes:
        normalized = unicodedata.normalize("NFC", identifier).strip().casefold()
        if not 1 <= len(normalized) <= 254 or not all(char.isprintable() for char in normalized):
            raise AuthenticationError("AUTH_CREDENTIAL_INVALID")
        context = f"camera-ai|LOOKUP-V1|identity-login|{tenant_id}|".encode()
        return hmac.new(self.key, context + normalized.encode(), hashlib.sha256).digest()


class Argon2idPasswordVerifier:
    """Argon2id verification with a startup-created unknown-user comparison hash."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()
        self._dummy_hash = self._hasher.hash("SYNTHETIC-DUMMY-CREDENTIAL-NOT-A-SECRET")

    @property
    def dummy_hash(self) -> str:
        return self._dummy_hash

    def hash(self, password: str) -> str:
        normalized = unicodedata.normalize("NFC", password)
        if not 15 <= len(normalized) <= 1024:
            raise AuthenticationError("AUTH_CREDENTIAL_INVALID")
        return self._hasher.hash(normalized)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            normalized = unicodedata.normalize("NFC", password)
            if not 1 <= len(normalized) <= 1024:
                return False
            return self._hasher.verify(password_hash, normalized)
        except (InvalidHashError, VerificationError):
            return False


@dataclass(frozen=True, slots=True)
class JwtAccessTokenCodec:
    """Strict, purpose-bound HS256 JWT adapter with caller-supplied secret material."""

    signing_key: bytes
    key_id: str
    issuer: str
    audience: str = "camera-ai-platform"
    lifetime: timedelta = timedelta(minutes=5)
    clock_skew: timedelta = timedelta(seconds=30)

    def __post_init__(self) -> None:
        if (
            len(self.signing_key) < 32
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,64}", self.key_id)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", self.issuer)
            or self.lifetime > timedelta(minutes=15)
            or self.lifetime <= timedelta()
            or not timedelta() <= self.clock_skew <= timedelta(seconds=60)
        ):
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE")

    def issue(self, *, session: SessionRecord, roles: frozenset[str], now: datetime) -> str:
        issued = int(now.timestamp())
        claims: dict[str, object] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": str(session.user_id),
            "sid": str(session.session_id),
            "fid": str(session.family_id),
            "tid": str(session.tenant_id),
            "roles": sorted(roles),
            "mfa": session.mfa_verified,
            "jti": str(uuid4()),
            "iat": issued,
            "nbf": issued,
            "exp": int((now + self.lifetime).timestamp()),
        }
        if session.school_id is not None:
            claims["school_id"] = str(session.school_id)
        return jwt.encode(
            claims,
            self.signing_key,
            algorithm="HS256",
            headers={"alg": "HS256", "typ": "JWT", "kid": self.key_id},
        )

    def verify(self, token: str, *, now: datetime) -> dict[str, object]:
        if not _TOKEN_PATTERN.fullmatch(token):
            raise AuthenticationError("AUTHENTICATION_REQUIRED")
        try:
            header = jwt.get_unverified_header(token)
            if header != {"alg": "HS256", "kid": self.key_id, "typ": "JWT"}:
                raise AuthenticationError("AUTHENTICATION_REQUIRED")
            claims = jwt.decode(
                token,
                self.signing_key,
                algorithms=["HS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "sid",
                        "fid",
                        "tid",
                        "jti",
                        "iat",
                        "nbf",
                        "exp",
                    ],
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
            issued = _integer_claim(claims, "iat")
            not_before = _integer_claim(claims, "nbf")
            expires = _integer_claim(claims, "exp")
            current = int(now.timestamp())
            skew = int(self.clock_skew.total_seconds())
            if (
                issued > current + skew
                or not_before > current + skew
                or expires <= current - skew
                or expires - issued > int(self.lifetime.total_seconds())
            ):
                raise AuthenticationError("AUTHENTICATION_REQUIRED")
            for claim in ("sub", "sid", "fid", "tid", "jti"):
                UUID(_string_claim(claims, claim))
            if "school_id" in claims:
                UUID(_string_claim(claims, "school_id"))
            role_values = claims.get("roles")
            if (
                not isinstance(role_values, list)
                or len(role_values) > 32
                or any(
                    not isinstance(role, str)
                    or re.fullmatch(r"[a-z][a-z0-9_.:-]{0,63}", role) is None
                    for role in role_values
                )
                or not isinstance(claims.get("mfa"), bool)
            ):
                raise AuthenticationError("AUTHENTICATION_REQUIRED")
            return dict(claims)
        except AuthenticationError:
            raise
        except Exception:
            raise AuthenticationError("AUTHENTICATION_REQUIRED") from None


def _integer_claim(claims: dict[str, object], name: str) -> int:
    value = claims.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuthenticationError("AUTHENTICATION_REQUIRED")
    return value


def _string_claim(claims: dict[str, object], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str):
        raise AuthenticationError("AUTHENTICATION_REQUIRED")
    return value


@dataclass(frozen=True, slots=True)
class Encv1MfaProtector:
    encryption: EncryptionService

    def protect(self, *, factor_id: UUID, tenant_id: UUID, secret: str) -> bytes:
        try:
            canonical = pyotp.TOTP(secret).secret
            return self.encryption.encrypt(
                canonical.encode(),
                self._binding(factor_id=factor_id, tenant_id=tenant_id),
            )
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None

    def reveal(self, factor: MfaFactor) -> str:
        try:
            plaintext = self.encryption.decrypt(
                factor.secret_ciphertext,
                self._binding(factor_id=factor.factor_id, tenant_id=factor.tenant_id),
            )
            return plaintext.decode("ascii")
        except Exception:
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE") from None
        finally:
            if "plaintext" in locals():
                del plaintext

    @staticmethod
    def _binding(*, factor_id: UUID, tenant_id: UUID) -> FieldBinding:
        return FieldBinding(
            service="identity-service",
            field_path="identity.mfa_factors.secret_ciphertext",
            record_id=factor_id,
            tenant_ref=str(tenant_id),
        )


class PyotpTotpVerifier:
    def verify(self, *, secret: str, code: str, now: datetime) -> bool:
        if not re.fullmatch(r"\d{6}", code):
            return False
        try:
            timestamp = now.astimezone(UTC)
            return bool(pyotp.TOTP(secret).verify(code, for_time=timestamp, valid_window=1))
        except Exception:
            return False


def validate_source_key(value: str) -> str:
    if _SOURCE_PATTERN.fullmatch(value) is None:
        raise AuthenticationError("AUTH_SOURCE_CONTEXT_REQUIRED")
    return value
