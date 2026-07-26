"""Canonical `ENCV1` envelope serialization and strict parsing.

Layout (big-endian lengths, no padding):

```text
magic          5 bytes   b"ENCV1"
algorithm      1 byte    0x01 = AES-256-GCM
aad_schema     1 byte    0x01 = v1
key_id_len     1 byte    1..64
key_id         n bytes   non-secret KMS/KEK identifier, ASCII
wrapped_len    2 bytes   wrap nonce + wrapped DEK + tag
wrapped_dek    n bytes
nonce         12 bytes   96-bit, unique per operation
ciphertext     rest      AEAD ciphertext concatenated with its 16-byte tag
```

Neither plaintext, DEK, KEK nor HMAC key material is ever present in the serialized form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from .errors import EnvelopeInvalidError

ENVELOPE_MAGIC: Final = b"ENCV1"
ALGORITHM_AES_256_GCM: Final = 1
AAD_SCHEMA_V1: Final = 1
NONCE_LENGTH: Final = 12
TAG_LENGTH: Final = 16
DEK_LENGTH: Final = 32
WRAPPED_DEK_LENGTH: Final = NONCE_LENGTH + DEK_LENGTH + TAG_LENGTH
MAX_KEY_ID_LENGTH: Final = 64
MAX_ENVELOPE_BYTES: Final = 1 << 20

_HEADER_FIXED_LENGTH: Final = len(ENVELOPE_MAGIC) + 3
_KEY_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def is_encv1_envelope(value: bytes) -> bool:
    """Return whether a byte string carries the ENCV1 magic prefix."""

    return value[: len(ENVELOPE_MAGIC)] == ENVELOPE_MAGIC


@dataclass(frozen=True, slots=True)
class Envelope:
    """Parsed envelope; carries no plaintext and no unwrapped key material."""

    key_id: str
    wrapped_dek: bytes
    nonce: bytes
    ciphertext: bytes
    algorithm: int = ALGORITHM_AES_256_GCM
    aad_schema: int = AAD_SCHEMA_V1

    def __post_init__(self) -> None:
        if (
            self.algorithm != ALGORITHM_AES_256_GCM
            or self.aad_schema != AAD_SCHEMA_V1
            or _KEY_ID_PATTERN.fullmatch(self.key_id) is None
            or len(self.wrapped_dek) != WRAPPED_DEK_LENGTH
            or len(self.nonce) != NONCE_LENGTH
            or len(self.ciphertext) < TAG_LENGTH
        ):
            raise EnvelopeInvalidError

    def serialize(self) -> bytes:
        """Return the canonical byte representation of this envelope."""

        key_id_bytes = self.key_id.encode("ascii")
        header = bytearray(ENVELOPE_MAGIC)
        header.append(self.algorithm)
        header.append(self.aad_schema)
        header.append(len(key_id_bytes))
        header.extend(key_id_bytes)
        header.extend(len(self.wrapped_dek).to_bytes(2, "big"))
        header.extend(self.wrapped_dek)
        header.extend(self.nonce)
        header.extend(self.ciphertext)
        return bytes(header)


def parse(value: bytes) -> Envelope:
    """Parse a serialized envelope under a strict size and version allowlist."""

    if len(value) > MAX_ENVELOPE_BYTES:
        raise EnvelopeInvalidError
    if len(value) < _HEADER_FIXED_LENGTH or not is_encv1_envelope(value):
        raise EnvelopeInvalidError

    cursor = len(ENVELOPE_MAGIC)
    algorithm = value[cursor]
    aad_schema = value[cursor + 1]
    key_id_length = value[cursor + 2]
    cursor += 3
    if key_id_length == 0 or key_id_length > MAX_KEY_ID_LENGTH:
        raise EnvelopeInvalidError

    key_id_end = cursor + key_id_length
    if len(value) < key_id_end + 2:
        raise EnvelopeInvalidError
    try:
        key_id = value[cursor:key_id_end].decode("ascii")
    except UnicodeDecodeError as error:
        raise EnvelopeInvalidError from error

    cursor = key_id_end
    wrapped_length = int.from_bytes(value[cursor : cursor + 2], "big")
    cursor += 2
    wrapped_end = cursor + wrapped_length
    if wrapped_length != WRAPPED_DEK_LENGTH or len(value) < wrapped_end + NONCE_LENGTH + TAG_LENGTH:
        raise EnvelopeInvalidError

    wrapped_dek = value[cursor:wrapped_end]
    nonce = value[wrapped_end : wrapped_end + NONCE_LENGTH]
    ciphertext = value[wrapped_end + NONCE_LENGTH :]
    return Envelope(
        key_id=key_id,
        wrapped_dek=wrapped_dek,
        nonce=nonce,
        ciphertext=ciphertext,
        algorithm=algorithm,
        aad_schema=aad_schema,
    )
