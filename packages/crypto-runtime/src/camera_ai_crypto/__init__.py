"""ENCV1 field encryption and LOOKUP-V1 exact-lookup runtime.

Import surface for services. Wiring a service with `UnavailableKeyProvider` (the default in the
port contract) makes every sensitive read and write fail closed instead of degrading to plaintext.
"""

from __future__ import annotations

from .aad import AAD_SCHEMA_V1, FieldBinding
from .envelope import ENVELOPE_MAGIC, Envelope, is_encv1_envelope, parse
from .errors import (
    AuthFailedError,
    CryptoError,
    CryptoErrorCode,
    EnvelopeInvalidError,
    KeyUnavailableError,
    LookupNormalizationError,
)
from .keys import (
    DeterministicFakeKeyProvider,
    KeyMaterial,
    KeyProvider,
    KeyState,
    SecretManagerKeyProvider,
    UnavailableKeyProvider,
)
from .lookup import LookupDomain, LookupHasher, NormalizationVersion, canonicalize
from .migrations import encv1_check_constraint, encv1_prefix_check
from .service import EncryptionService

__all__ = [
    "AAD_SCHEMA_V1",
    "ENVELOPE_MAGIC",
    "AuthFailedError",
    "CryptoError",
    "CryptoErrorCode",
    "DeterministicFakeKeyProvider",
    "EncryptionService",
    "Envelope",
    "EnvelopeInvalidError",
    "FieldBinding",
    "KeyMaterial",
    "KeyProvider",
    "KeyState",
    "KeyUnavailableError",
    "LookupDomain",
    "LookupHasher",
    "LookupNormalizationError",
    "NormalizationVersion",
    "SecretManagerKeyProvider",
    "UnavailableKeyProvider",
    "canonicalize",
    "encv1_check_constraint",
    "encv1_prefix_check",
    "is_encv1_envelope",
    "parse",
]
