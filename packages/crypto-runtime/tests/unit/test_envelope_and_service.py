"""ENCV1 envelope, encryption service, rotation and fail-closed behaviour.

All keys and values here are synthetic. No real personal, biometric, credential or production
data is used, and no test asserts on plaintext recovered from a fixture of real data.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from camera_ai_crypto import (
    ENVELOPE_MAGIC,
    AuthFailedError,
    DeterministicFakeKeyProvider,
    EncryptionService,
    EnvelopeInvalidError,
    FieldBinding,
    KeyState,
    KeyUnavailableError,
    UnavailableKeyProvider,
    is_encv1_envelope,
    parse,
)

SEED = b"synthetic-test-seed-not-a-real-key"
TENANT = "tenant_test_0001"
OTHER_TENANT = "tenant_test_0002"
RECORD = UUID("00000000-0000-4000-8000-000000000001")
OTHER_RECORD = UUID("00000000-0000-4000-8000-000000000002")
PLAINTEXT = b"synthetic-field-value"


def binding(
    *,
    tenant: str = TENANT,
    record: UUID = RECORD,
    field_path: str = "school.students.full_name_ciphertext",
    service: str = "school-service",
) -> FieldBinding:
    return FieldBinding(
        service=service,
        field_path=field_path,
        record_id=record,
        tenant_ref=tenant,
    )


def make_service() -> EncryptionService:
    return EncryptionService(key_provider=DeterministicFakeKeyProvider(seed=SEED))


def test_round_trip_returns_plaintext_and_marks_envelope() -> None:
    service = make_service()

    envelope = service.encrypt(PLAINTEXT, binding())

    assert is_encv1_envelope(envelope)
    assert envelope[: len(ENVELOPE_MAGIC)] == ENVELOPE_MAGIC
    assert PLAINTEXT not in envelope
    assert service.decrypt(envelope, binding()) == PLAINTEXT


def test_ciphertext_is_non_deterministic_across_calls() -> None:
    service = make_service()

    first = service.encrypt(PLAINTEXT, binding())
    second = service.encrypt(PLAINTEXT, binding())

    assert first != second
    assert parse(first).nonce != parse(second).nonce
    assert parse(first).wrapped_dek != parse(second).wrapped_dek


def test_empty_plaintext_round_trips_without_special_casing() -> None:
    service = make_service()

    envelope = service.encrypt(b"", binding())

    assert service.decrypt(envelope, binding()) == b""


@pytest.mark.parametrize("offset", [5, 40, -1])
def test_tampered_bytes_fail_authentication(offset: int) -> None:
    service = make_service()
    envelope = bytearray(service.encrypt(PLAINTEXT, binding()))
    envelope[offset] ^= 0x01

    with pytest.raises((AuthFailedError, EnvelopeInvalidError)):
        service.decrypt(bytes(envelope), binding())


def test_cross_record_ciphertext_swap_fails_authentication() -> None:
    service = make_service()
    envelope = service.encrypt(PLAINTEXT, binding())

    with pytest.raises(AuthFailedError):
        service.decrypt(envelope, binding(record=OTHER_RECORD))


def test_cross_tenant_ciphertext_swap_fails_authentication() -> None:
    service = make_service()
    envelope = service.encrypt(PLAINTEXT, binding())

    with pytest.raises(AuthFailedError):
        service.decrypt(envelope, binding(tenant=OTHER_TENANT))


def test_cross_field_and_cross_service_binding_fails_authentication() -> None:
    service = make_service()
    envelope = service.encrypt(PLAINTEXT, binding())

    with pytest.raises(AuthFailedError):
        service.decrypt(envelope, binding(field_path="school.students.date_of_birth_ciphertext"))
    with pytest.raises(AuthFailedError):
        service.decrypt(envelope, binding(service="identity-service"))


@pytest.mark.parametrize("keep", [0, 4, 16, 63])
def test_truncated_envelope_is_rejected(keep: int) -> None:
    service = make_service()
    envelope = service.encrypt(PLAINTEXT, binding())

    with pytest.raises(EnvelopeInvalidError):
        service.decrypt(envelope[:keep], binding())


def test_plaintext_masquerading_as_ciphertext_is_rejected() -> None:
    service = make_service()

    with pytest.raises(EnvelopeInvalidError):
        service.decrypt(b"plaintext full name that a buggy writer stored directly", binding())


def test_unwired_provider_denies_every_operation() -> None:
    wired = make_service()
    envelope = wired.encrypt(PLAINTEXT, binding())
    service = EncryptionService(key_provider=UnavailableKeyProvider())

    with pytest.raises(KeyUnavailableError):
        service.encrypt(PLAINTEXT, binding())
    with pytest.raises(KeyUnavailableError):
        service.decrypt(envelope, binding())


def test_disabled_key_denies_decrypt_without_plaintext_fallback() -> None:
    provider = DeterministicFakeKeyProvider(seed=SEED)
    service = EncryptionService(key_provider=provider)
    envelope = service.encrypt(PLAINTEXT, binding())
    provider.register("fake-key-v1", KeyState.DISABLED)

    with pytest.raises(KeyUnavailableError):
        service.decrypt(envelope, binding())


def test_dual_read_current_write_rotation_and_rewrap() -> None:
    provider = DeterministicFakeKeyProvider(seed=SEED)
    service = EncryptionService(key_provider=provider)
    old_envelope = service.encrypt(PLAINTEXT, binding())

    provider.register("fake-key-v1", KeyState.DECRYPT_ONLY)
    provider.register("fake-key-v2", KeyState.ACTIVE)
    provider.current = "fake-key-v2"

    assert service.decrypt(old_envelope, binding()) == PLAINTEXT

    new_envelope = service.rewrap(old_envelope, binding())

    assert parse(old_envelope).key_id == "fake-key-v1"
    assert parse(new_envelope).key_id == "fake-key-v2"
    assert service.decrypt(new_envelope, binding()) == PLAINTEXT


def test_decrypt_only_key_cannot_be_used_for_new_writes() -> None:
    provider = DeterministicFakeKeyProvider(seed=SEED)
    provider.register("fake-key-v1", KeyState.DECRYPT_ONLY)
    service = EncryptionService(key_provider=provider)

    with pytest.raises(KeyUnavailableError):
        service.encrypt(PLAINTEXT, binding())


def test_errors_and_repr_never_reveal_plaintext_or_key_material() -> None:
    provider = DeterministicFakeKeyProvider(seed=SEED)
    service = EncryptionService(key_provider=provider)
    envelope = service.encrypt(PLAINTEXT, binding())
    key_material = provider.resolve("fake-key-v1").material

    try:
        service.decrypt(envelope, binding(tenant=OTHER_TENANT))
    except AuthFailedError as error:
        rendered = f"{error!s} {error!r}"
    else:  # pragma: no cover - the swap must fail
        raise AssertionError("expected authentication failure")

    assert rendered == "ENCRYPTION_AUTH_FAILED AuthFailedError(code=ENCRYPTION_AUTH_FAILED)"
    assert PLAINTEXT.decode() not in rendered
    assert key_material.hex() not in rendered
    assert TENANT not in rendered


def test_binding_rejects_malformed_coordinates() -> None:
    with pytest.raises(ValueError, match="invalid field path"):
        binding(field_path="students")
    with pytest.raises(ValueError, match="invalid service reference"):
        binding(service="School Service")


def test_unique_record_ids_produce_isolated_ciphertext() -> None:
    service = make_service()
    first = service.encrypt(PLAINTEXT, binding(record=uuid4()))
    second_binding = binding(record=uuid4())

    with pytest.raises(AuthFailedError):
        service.decrypt(first, second_binding)
