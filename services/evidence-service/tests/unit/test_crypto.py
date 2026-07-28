from __future__ import annotations

from uuid import UUID

import pytest
from camera_ai_crypto import DeterministicFakeKeyProvider, EncryptionService
from evidence_service.domain.errors import EvidenceError
from evidence_service.infrastructure.crypto import CryptoObjectLocatorProtector

EVIDENCE_ID = UUID("00000000-0000-4000-8000-000000006701")
TENANT_ID = UUID("00000000-0000-4000-8000-000000006702")
OTHER_TENANT_ID = UUID("00000000-0000-4000-8000-000000006703")


def protector() -> CryptoObjectLocatorProtector:
    return CryptoObjectLocatorProtector(
        EncryptionService(
            DeterministicFakeKeyProvider(seed=b"synthetic-evidence-test-seed-not-a-real-key")
        )
    )


def test_object_key_and_provider_version_are_encv1_and_context_bound() -> None:
    adapter = protector()
    object_key = "evidence/v1/ab/ab000000000000000000000000000001"
    key_ciphertext, version_ciphertext = adapter.protect(
        evidence_id=EVIDENCE_ID,
        tenant_id=TENANT_ID,
        object_key=object_key,
        provider_version="synthetic-version-1",
    )

    assert key_ciphertext.startswith(b"ENCV1")
    assert version_ciphertext is not None and version_ciphertext.startswith(b"ENCV1")
    assert object_key.encode() not in key_ciphertext
    assert adapter.reveal(
        evidence_id=EVIDENCE_ID,
        tenant_id=TENANT_ID,
        object_key_ciphertext=key_ciphertext,
        provider_version_ciphertext=version_ciphertext,
    ) == (object_key, "synthetic-version-1")

    with pytest.raises(EvidenceError, match="EVIDENCE_CRYPTO_UNAVAILABLE"):
        adapter.reveal(
            evidence_id=EVIDENCE_ID,
            tenant_id=OTHER_TENANT_ID,
            object_key_ciphertext=key_ciphertext,
            provider_version_ciphertext=version_ciphertext,
        )
