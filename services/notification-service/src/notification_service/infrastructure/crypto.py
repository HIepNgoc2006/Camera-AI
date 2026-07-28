"""ENCV1 and LOOKUP-V1 adapter for notification recipient endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from camera_ai_crypto import (
    EncryptionService,
    FieldBinding,
    LookupDomain,
    LookupHasher,
    NormalizationVersion,
)

from notification_service.domain.errors import NotificationError


@dataclass(frozen=True, slots=True)
class CryptoEndpointProtector:
    encryption: EncryptionService
    lookup: LookupHasher

    def protect(
        self,
        *,
        endpoint_id: UUID,
        tenant_id: UUID,
        recipient_ref: UUID,
        kind: str,
        value: str | bytes,
    ) -> tuple[bytes, bytes]:
        del recipient_ref
        try:
            if kind == "device_token":
                version = NormalizationVersion.DEVICE_TOKEN_V1
                domain_name = "notification-device-token"
                if not isinstance(value, bytes):
                    raise NotificationError("NOTIFICATION_REQUEST_INVALID")
                plaintext = value
            elif kind == "email":
                version = NormalizationVersion.EMAIL_V1
                domain_name = "notification-recipient-email"
                if not isinstance(value, str):
                    raise NotificationError("NOTIFICATION_REQUEST_INVALID")
                plaintext = value.encode("utf-8")
            else:
                raise NotificationError("NOTIFICATION_REQUEST_INVALID")
            binding = FieldBinding(
                service="notification-service",
                field_path="notification.recipient_endpoints.endpoint_ciphertext",
                record_id=endpoint_id,
                tenant_ref=str(tenant_id),
            )
            ciphertext = self.encryption.encrypt(plaintext, binding)
            digest = self.lookup.digest(
                value,
                LookupDomain(
                    name=domain_name,
                    tenant_ref=str(tenant_id),
                    version=version,
                ),
            )
            return ciphertext, digest
        except NotificationError:
            raise
        except Exception:
            raise NotificationError("NOTIFICATION_DEPENDENCY_UNAVAILABLE") from None
        finally:
            if "plaintext" in locals():
                del plaintext
