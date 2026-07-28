"""ENCV1 protection for object keys and provider version identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from camera_ai_crypto import EncryptionService, FieldBinding, parse

from evidence_service.domain.errors import EvidenceError


@dataclass(frozen=True, slots=True)
class CryptoObjectLocatorProtector:
    encryption: EncryptionService

    @staticmethod
    def _binding(
        *,
        evidence_id: UUID,
        tenant_id: UUID,
        field_path: str,
    ) -> FieldBinding:
        return FieldBinding(
            service="evidence-storage-service",
            field_path=field_path,
            record_id=evidence_id,
            tenant_ref=str(tenant_id),
        )

    def protect(
        self,
        *,
        evidence_id: UUID,
        tenant_id: UUID,
        object_key: str,
        provider_version: str | None,
    ) -> tuple[bytes, bytes | None]:
        try:
            key_ciphertext = self.encryption.encrypt(
                object_key.encode("ascii"),
                self._binding(
                    evidence_id=evidence_id,
                    tenant_id=tenant_id,
                    field_path="evidence.evidence_objects.object_key_ciphertext",
                ),
            )
            version_ciphertext = (
                None
                if provider_version is None
                else self.encryption.encrypt(
                    provider_version.encode("utf-8"),
                    self._binding(
                        evidence_id=evidence_id,
                        tenant_id=tenant_id,
                        field_path="evidence.evidence_objects.provider_version_ciphertext",
                    ),
                )
            )
            return key_ciphertext, version_ciphertext
        except Exception:
            raise EvidenceError("EVIDENCE_CRYPTO_UNAVAILABLE") from None

    def reveal(
        self,
        *,
        evidence_id: UUID,
        tenant_id: UUID,
        object_key_ciphertext: bytes,
        provider_version_ciphertext: bytes | None,
    ) -> tuple[str, str | None]:
        try:
            key_plaintext = self.encryption.decrypt(
                object_key_ciphertext,
                self._binding(
                    evidence_id=evidence_id,
                    tenant_id=tenant_id,
                    field_path="evidence.evidence_objects.object_key_ciphertext",
                ),
            )
            version_plaintext = (
                None
                if provider_version_ciphertext is None
                else self.encryption.decrypt(
                    provider_version_ciphertext,
                    self._binding(
                        evidence_id=evidence_id,
                        tenant_id=tenant_id,
                        field_path="evidence.evidence_objects.provider_version_ciphertext",
                    ),
                )
            )
            object_key = key_plaintext.decode("ascii")
            provider_version = (
                None if version_plaintext is None else version_plaintext.decode("utf-8")
            )
            if not object_key.startswith("evidence/v1/"):
                raise EvidenceError("EVIDENCE_LOCATOR_INVALID")
            return object_key, provider_version
        except EvidenceError:
            raise
        except Exception:
            raise EvidenceError("EVIDENCE_CRYPTO_UNAVAILABLE") from None
        finally:
            if "key_plaintext" in locals():
                del key_plaintext
            if "version_plaintext" in locals():
                del version_plaintext

    def key_version(self, ciphertext: bytes) -> str:
        try:
            return parse(ciphertext).key_id
        except Exception:
            raise EvidenceError("EVIDENCE_CRYPTO_UNAVAILABLE") from None
