"""Key provider port and adapters.

The runtime never reads key material from PostgreSQL, `.env` files, fixtures or logs. A provider
resolves a non-secret `key_id` to key-encryption-key material held by a KMS or secret manager.
Writes use exactly one current key; reads accept a finite allowlist of current plus `decrypt_only`
keys so dual-read/current-write rotation is possible without a plaintext window.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

from .errors import KeyUnavailableError

KEK_LENGTH = 32


class KeyState(StrEnum):
    """Lifecycle states that decide whether a key may encrypt, decrypt, or neither."""

    ACTIVE = "active"
    DECRYPT_ONLY = "decrypt_only"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class KeyMaterial:
    """Key-encryption-key bytes plus the lifecycle state of its `key_id`."""

    key_id: str
    state: KeyState
    material: bytes

    def __post_init__(self) -> None:
        if len(self.material) != KEK_LENGTH:
            raise KeyUnavailableError


class KeyProvider(Protocol):
    """Port implemented by KMS/secret-manager adapters."""

    def current_key_id(self) -> str:
        """Return the `key_id` that new ciphertext must be written under."""

    def resolve(self, key_id: str) -> KeyMaterial:
        """Return key material for `key_id`, or raise `KeyUnavailableError`."""


@dataclass(slots=True)
class UnavailableKeyProvider:
    """Fail-closed default: every call raises, so an unwired service cannot write plaintext."""

    def current_key_id(self) -> str:
        raise KeyUnavailableError

    def resolve(self, key_id: str) -> KeyMaterial:
        raise KeyUnavailableError


@dataclass(slots=True)
class DeterministicFakeKeyProvider:
    """Local and test provider deriving fake key material from a non-production seed.

    Never use in staging or production: the seed is not a managed key and the derivation is
    intentionally reproducible so tests can assert rotation behaviour.
    """

    seed: bytes
    current: str = "fake-key-v1"
    states: dict[str, KeyState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.seed) < 16:
            raise KeyUnavailableError
        self.states.setdefault(self.current, KeyState.ACTIVE)

    def register(self, key_id: str, state: KeyState) -> None:
        """Add or update a fake key so rotation windows can be exercised."""

        self.states[key_id] = state

    def current_key_id(self) -> str:
        state = self.states.get(self.current)
        if state is not KeyState.ACTIVE:
            raise KeyUnavailableError
        return self.current

    def resolve(self, key_id: str) -> KeyMaterial:
        state = self.states.get(key_id)
        if state is None or state is KeyState.DISABLED:
            raise KeyUnavailableError
        material = hmac.new(self.seed, key_id.encode("ascii"), sha256).digest()
        return KeyMaterial(key_id=key_id, state=state, material=material)


@dataclass(slots=True)
class SecretManagerKeyProvider:
    """Adapter seam for the approved secret manager; fails closed until a resolver is injected.

    The resolver is supplied by the deployment wiring and returns KEK bytes for a `key_id`. No
    default resolver exists on purpose: a missing integration must deny, never degrade.
    """

    current: str
    resolver: Callable[[str], bytes] | None = None
    states: dict[str, KeyState] = field(default_factory=dict)

    def current_key_id(self) -> str:
        if self.resolver is None or self.states.get(self.current) is not KeyState.ACTIVE:
            raise KeyUnavailableError
        return self.current

    def resolve(self, key_id: str) -> KeyMaterial:
        resolver = self.resolver
        state = self.states.get(key_id)
        if resolver is None or state is None or state is KeyState.DISABLED:
            raise KeyUnavailableError
        try:
            material = resolver(key_id)
        except Exception as error:
            raise KeyUnavailableError from error
        return KeyMaterial(key_id=key_id, state=state, material=material)
