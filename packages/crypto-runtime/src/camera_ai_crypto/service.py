"""Envelope encryption service: encrypt, decrypt and rewrap `ENCV1` field values.

Every operation generates a fresh data-encryption key and a fresh 96-bit nonce, so a nonce is
never reused under one key. The DEK is wrapped by the key-encryption key resolved from the key
provider, and both the wrap and the payload are bound to the same `aad_schema=v1` coordinates,
so moving ciphertext to another record, tenant or field fails authentication.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .aad import FieldBinding
from .envelope import (
    ALGORITHM_AES_256_GCM,
    DEK_LENGTH,
    NONCE_LENGTH,
    Envelope,
    parse,
)
from .errors import AuthFailedError, EnvelopeInvalidError, KeyUnavailableError
from .keys import KeyProvider, KeyState

_WRAP_CONTEXT = b"camera-ai|ENCV1|dek-wrap|v1"


@dataclass(frozen=True, slots=True)
class EncryptionService:
    """Field-level encryption bound to a key provider; holds no key material itself."""

    key_provider: KeyProvider

    def encrypt(self, plaintext: bytes, binding: FieldBinding) -> bytes:
        """Encrypt one field value and return its serialized envelope."""

        key_id = self.key_provider.current_key_id()
        key = self.key_provider.resolve(key_id)
        if key.state is not KeyState.ACTIVE:
            raise KeyUnavailableError

        aad = binding.to_aad()
        dek = os.urandom(DEK_LENGTH)
        wrap_nonce = os.urandom(NONCE_LENGTH)
        wrapped = AESGCM(key.material).encrypt(wrap_nonce, dek, _WRAP_CONTEXT + aad)
        nonce = os.urandom(NONCE_LENGTH)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
        envelope = Envelope(
            key_id=key_id,
            wrapped_dek=wrap_nonce + wrapped,
            nonce=nonce,
            ciphertext=ciphertext,
            algorithm=ALGORITHM_AES_256_GCM,
        )
        return envelope.serialize()

    def decrypt(self, value: bytes, binding: FieldBinding) -> bytes:
        """Decrypt a serialized envelope after verifying its authentication tag."""

        envelope = parse(value)
        key = self.key_provider.resolve(envelope.key_id)
        if key.state is KeyState.DISABLED:
            raise KeyUnavailableError

        aad = binding.to_aad()
        wrap_nonce = envelope.wrapped_dek[:NONCE_LENGTH]
        wrapped = envelope.wrapped_dek[NONCE_LENGTH:]
        try:
            dek = AESGCM(key.material).decrypt(wrap_nonce, wrapped, _WRAP_CONTEXT + aad)
        except InvalidTag as error:
            raise AuthFailedError from error
        if len(dek) != DEK_LENGTH:
            raise EnvelopeInvalidError
        try:
            return AESGCM(dek).decrypt(envelope.nonce, envelope.ciphertext, aad)
        except InvalidTag as error:
            raise AuthFailedError from error

    def rewrap(self, value: bytes, binding: FieldBinding) -> bytes:
        """Re-encrypt an existing envelope under the current key without exposing plaintext.

        Rotation is dual-read/current-write: the previous key must still resolve for decrypt,
        while the result is always written under the current key.
        """

        plaintext = self.decrypt(value, binding)
        try:
            return self.encrypt(plaintext, binding)
        finally:
            del plaintext
